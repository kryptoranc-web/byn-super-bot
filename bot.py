import os
import logging
import asyncio
import signal
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# --- Импорты ваших модулей ---
from parser import CurrencyParser
from analyzer import TechnicalAnalyzer
from ai_forecast import AIForecast
from users_db import UserDB
from subscription import get_subscription_status, get_trial_end_date, TRIAL_DAYS, is_valid_referral
from payments import generate_erip_payment
from languages import LANGUAGES
from config import CITIES
from agreement import WELCOME_TEXT, AGREEMENT_TEXT, welcome_keyboard, agreement_keyboard, legal_disclaimer
from admin_panel import admin_router, is_admin, get_admin_reply_keyboard, check_user_access, ADMIN_ID

# --- Инициализация ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("BYN-Super-Bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(admin_router)

# --- Глобальное состояние ---
CACHE_DATA = {"nbrb": {}, "banks": {}, "forex": {}}
cache_lock = asyncio.Lock()
USER_LAST_MESSAGE = {}

# --- Middleware: Защита от спама с очисткой памяти ---
class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[types.Message, Dict[str, Any]], Awaitable[Any]], 
                       event: types.Message, data: Dict[str, Any]) -> Any:
        user_id = event.from_user.id
        now = datetime.now()
        last = USER_LAST_MESSAGE.get(user_id, datetime.min)
        
        # Очистка словаря памяти, если он разросся
        if len(USER_LAST_MESSAGE) > 2000:
            USER_LAST_MESSAGE.clear()
            
        if (now - last).total_seconds() < 0.8: # Лимит 0.8 сек на сообщение
            return 
        USER_LAST_MESSAGE[user_id] = now
        return await handler(event, data)

dp.message.middleware(ThrottlingMiddleware())

# --- Логика ---
parser = CurrencyParser()
ai = AIForecast()
db = UserDB()

async def update_data_loop():
    """Фоновое обновление с жесткими таймаутами."""
    while True:
        try:
            # Таймаут 30 секунд на весь цикл парсинга
            async with asyncio.timeout(30):
                nbrb = await parser.get_nbrb_rates()
                forex = await parser.get_forex_data()
                new_banks = {city: await parser.get_bank_rates_for_city(city) for city in CITIES}
                
                async with cache_lock:
                    CACHE_DATA.update({"nbrb": nbrb, "banks": new_banks, "forex": forex})
                logger.info("✅ Данные обновлены")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления: {e}")
        await asyncio.sleep(1800)

def format_forecast(forecast, city, all_banks):
    try:
        curr = forecast.get("currency", "USD")
        text = f"╔════════════════════════════════════════════════╗\n" \
               f" ║        ⚡ QUANTUM FX INTELLIGENCE v4.3         ║\n" \
               f"╚════════════════════════════════════════════════╝\n\n" \
               f" 🎯 АКТИВ: {curr}/BYN | РЕКОМЕНДАЦИЯ: {forecast.get('recommendation', 'ДЕРЖАТЬ ⏳')}\n" \
               f" ══════════════════════════════════════════════════\n" \
               f" 🏦 БАНКИ ({city.upper()}):\n" \
               f"| № | Банк | Покупка/Продажа |\n|---|---|---|\n"
        
        for i, b in enumerate(all_banks[:5], 1):
            text += f"| {i} | {b.get('name', 'Банк')[:8]} | {b.get('buy', '—')} / {b.get('sell', '—')} |\n"
        
        return text + "\n" + legal_disclaimer()
    except Exception:
        return "⚠️ Ошибка данных."

# --- Обработчики ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("👑 Админ", reply_markup=get_admin_reply_keyboard())
    else:
        await message.answer(WELCOME_TEXT, reply_markup=welcome_keyboard())

@dp.message(F.text == "🏦 Курсы в банках")
async def banks_handler(message: types.Message):
    async with cache_lock:
        banks = CACHE_DATA.get("banks", {}).get(db.get_city(message.from_user.id), {})
    if not banks:
        await message.answer("🔄 Загрузка...")
        return
    resp = "🏦 *Курсы:*\n" + "".join([f"📌 {n}: USD {d.get('USD', {}).get('buy', '—')}\n" for n, d in list(banks.items())[:10]])
    await message.answer(resp, parse_mode="Markdown")

@dp.message(F.text.startswith("🤖 AI-Прогноз"))
async def ai_handler(message: types.Message):
    if not check_user_access(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return
    async with cache_lock:
        all_banks = sum(CACHE_DATA.get("banks", {}).get(db.get_city(message.from_user.id), {}).values(), [])
    forecast = await ai.generate_forecast("USD", 3.0, [], all_banks)
    await message.answer(format_forecast(forecast, db.get_city(message.from_user.id), all_banks), parse_mode="Markdown")

# --- Запуск ---
async def start_web_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Running"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

async def shutdown():
    logger.info("🛑 Остановка...")
    asyncio.get_running_loop().stop()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Сигналы остановки
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    
    try:
        loop.run_until_complete(asyncio.gather(update_data_loop(), start_web_server(), dp.start_polling(bot)))
    except Exception as e:
        logger.critical(f"FATAL ERROR: {e}")
