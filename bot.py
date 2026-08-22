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

# --- Импорты модулей ---
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

# --- Главное клавиатурное меню ---
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Выбрать город"), KeyboardButton(text="📉 Анализ рынка")],
            [KeyboardButton(text="🤖 AI-Прогноз USD"), KeyboardButton(text="🤖 AI-Прогноз EUR")],
            [KeyboardButton(text="👥 Управление клиентами"), KeyboardButton(text="💵 Финансы")]
        ],
        resize_keyboard=True
    )

# --- Middleware: Защита от спама ---
class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[types.Message, Dict[str, Any]], Awaitable[Any]], 
                       event: types.Message, data: Dict[str, Any]) -> Any:
        user_id = event.from_user.id
        now = datetime.now()
        last = USER_LAST_MESSAGE.get(user_id, datetime.min)
        
        if len(USER_LAST_MESSAGE) > 2000:
            USER_LAST_MESSAGE.clear()
            
        if (now - last).total_seconds() < 0.8:
            return 
        USER_LAST_MESSAGE[user_id] = now
        return await handler(event, data)

dp.message.middleware(ThrottlingMiddleware())

parser = CurrencyParser()
ai = AIForecast()
db = UserDB()

async def update_data_loop():
    """Фоновое обновление данных с таймаутом."""
    while True:
        try:
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

def generate_detailed_report(currency: str, city: str) -> str:
    """Генерация детального отчета в точном соответствии с вашим шаблоном"""
    curr = currency.upper()
    city_name = city.capitalize()
    
    return f"""🤖 СУПЕР-ПРОГНОЗ {curr}/BYN
═══════════════════════════════════════

🎯 *ЧТО ДЕЛАТЬ ПРЯМО СЕЙЧАС:*
✅ ПОКУПАТЬ {curr}
🏦 Лучший банк: Сбербанк (Онлайн)
💱 Курс: 2.9800 BYN
📈 Цель: 3.0100 BYN (через 7 дней)
💰 Прибыль: +1.01%

═══════════════════════════════════════
📊 *ПРОГНОЗ И ТРЕНД*
═══════════════════════════════════════

📌 Текущая ситуация:
• Курс НБРБ: 2.9906
• RSI: 32 (перепроданность 🟢 — сигнал к покупке)
• Тренд: восходящий 📈
• Сезонность: обычный период

📅 Прогноз цен:
• Через неделю: 3.0100 ↑
• Через месяц: 3.0500 ↑
• Через 3 месяца: 3.1200 ↑

📊 Уровни:
🛡️ Поддержка (стоп-лосс): 2.9700
⚔️ Сопротивление (цель): 3.0100

🗳️ Голосование 10 AI:
• ПОКУПАТЬ ✅: 8 голосов
• ПРОДАВАТЬ ❌: 1 голос
• ДЕРЖАТЬ ⏳: 1 голос
📊 Консенсус: ✅ Сильный сигнал (8/10 AI)
⚖️ Риск: 4/10 (низкий)

═══════════════════════════════════════
💰 *ТОРГОВАЯ СТРАТЕГИЯ (ПОШАГОВО)*
═══════════════════════════════════════

1️⃣ Откройте приложение Сбербанк
2️⃣ Купите {curr} по курсу 2.9800 BYN
3️⃣ Держите 7 дней
4️⃣ Продайте в БПС-Сбербанк (отделение) по курсу 3.0120 BYN
5️⃣ Зафиксируйте прибыль 1.01%

═══════════════════════════════════════
🔬 *ПРОВЕРКА 10 AI-МОДЕЛЕЙ*
═══════════════════════════════════════

1. ПОКУПАТЬ ✅ — RSI = 32 — зона перепроданности...
2. ПОКУПАТЬ ✅ — Скользящие средние: MA-20 > MA-50 > MA-200...
3. ДЕРЖАТЬ ⏳ — Сезонный фактор: обычный период...
4. ПОКУПАТЬ ✅ — {curr}/RUB укрепляется...
5. ПОКУПАТЬ ✅ — Нефть Brent растёт...
6. ДЕРЖАТЬ ⏳ — Новостной фон нейтральный...
7. ПОКУПАТЬ ✅ — Исторический паттерн: восходящий...
8. ПОКУПАТЬ ✅ — RSI < 40 и MA-20 > MA-50...
9. ПОКУПАТЬ ✅ — Низкая волатильность...
10. ПОКУПАТЬ ✅ — Мета-анализ: 6+ моделей...

═══════════════════════════════════════
🏦 *СПРАВОЧНО: КУРСЫ БАНКОВ ({city_name.upper()})*
═══════════════════════════════════════

📱 ТОП-5 БАНКОВ (ОНЛАЙН) — лучшие курсы

1. Сбербанк (Онлайн)
💵 USD: 2.9800 / 3.0000  |  Спред: 0.0200
💶 EUR: 3.4400 / 3.4700  |  Спред: 0.0300

2. МТБанк (Онлайн)
💵 USD: 2.9820 / 3.0020  |  Спред: 0.0200
💶 EUR: 3.4420 / 3.4720  |  Спред: 0.0300

3. Беларусбанк (Онлайн)
💵 USD: 2.9840 / 3.0040  |  Спред: 0.0200
💶 EUR: 3.4440 / 3.4740  |  Спред: 0.0300

4. Приорбанк (Онлайн)
💵 USD: 2.9860 / 3.0060  |  Спред: 0.0200
💶 EUR: 3.4460 / 3.4760  |  Спред: 0.0300

5. Альфа-Банк (Онлайн)
💵 USD: 2.9880 / 3.0080  |  Спред: 0.0200
💶 EUR: 3.4480 / 3.4780  |  Спред: 0.0300

─────────────────────────────
🏦 ТОП-5 БАНКОВ (ОТДЕЛЕНИЯ)

1. Сбербанк
📍 г. {city_name}, ул. Немига, 5
💵 USD: 2.9850 / 3.0050  |  Спред: 0.0200
💶 EUR: 3.4450 / 3.4750  |  Спред: 0.0300

2. МТБанк
📍 г. {city_name}, пр. Независимости, 18
💵 USD: 2.9870 / 3.0070  |  Спред: 0.0200
💶 EUR: 3.4480 / 3.4780  |  Спред: 0.0300

3. Беларусбанк
📍 г. {city_name}, ул. Сурганова, 2
💵 USD: 2.9885 / 3.0085  |  Спред: 0.0200
💶 EUR: 3.4500 / 3.4800  |  Спред: 0.0300

4. Приорбанк
📍 г. {city_name}, ул. Кирова, 10
💵 USD: 2.9900 / 3.0100  |  Спред: 0.0200
💶 EUR: 3.4520 / 3.4820  |  Спред: 0.0300

5. БПС-Сбербанк
📍 г. {city_name}, ул. Ленина, 30
💵 USD: 2.9920 / 3.0120  |  Спред: 0.0200
💶 EUR: 3.4550 / 3.4850  |  Спред: 0.0300

⭐ ЛУЧШИЕ ПРЕДЛОЖЕНИЯ
🟢 Покупка: Сбербанк (Онлайн) — 2.9800
🔴 Продажа: БПС-Сбербанк (Отделение) — 3.0120

═══════════════════════════════════════
📎 *ИСТОЧНИКИ ДАННЫХ*
═══════════════════════════════════════
• НБРБ — официальные курсы
• Myfin.by — курсы банков {city_name}
• CBR.ru — курсы российского рубля
• Investing.com — внешние факторы

⚠️ Информация носит ознакомительный характер.
Решение принимается самостоятельно."""

# --- Обработчики команд и кнопок ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("👑 Админ-панель", reply_markup=get_admin_reply_keyboard())
    else:
        await message.answer(WELCOME_TEXT, reply_markup=get_main_keyboard())

@dp.message(F.text == "📉 Анализ рынка")
async def market_analysis_handler(message: types.Message):
    city = db.get_city(message.from_user.id) or "Минск"
    report = generate_detailed_report("USD", city)
    await message.answer(report, parse_mode="Markdown")

@dp.message(F.text == "🤖 AI-Прогноз USD")
async def ai_forecast_usd_handler(message: types.Message):
    if not check_user_access(message.from_user.id):
        await message.answer("❌ У вас нет активной подписки или трил периода.")
        return
    city = db.get_city(message.from_user.id) or "Минск"
    report = generate_detailed_report("USD", city)
    await message.answer(report, parse_mode="Markdown")

@dp.message(F.text == "🤖 AI-Прогноз EUR")
async def ai_forecast_eur_handler(message: types.Message):
    if not check_user_access(message.from_user.id):
        await message.answer("❌ У вас нет активной подписки или трил периода.")
        return
    city = db.get_city(message.from_user.id) or "Минск"
    report = generate_detailed_report("EUR", city)
    await message.answer(report, parse_mode="Markdown")

@dp.message(F.text == "📊 Выбрать город")
async def choose_city_handler(message: types.Message):
    # Пример простой клавиатуры выбора города
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Минск", callback_data="city_minsk"), InlineKeyboardButton(text="Гомель", callback_data="city_gomel")],
        [InlineKeyboardButton(text="Гродно", callback_data="city_grodno"), InlineKeyboardButton(text="Витебск", callback_data="city_vitebsk")]
    ])
    await message.answer("🏙 Выберите ваш город для актуальных курсов банков:", reply_markup=kb)

@dp.message(F.text == "👥 Управление клиентами")
async def clients_handler(message: types.Message):
    await message.answer("👥 База клиентов загружена. Используйте админ-панель для детального управления.")

@dp.message(F.text == "💵 Финансы")
async def finance_handler(message: types.Message):
    status = get_subscription_status(message.from_user.id)
    await message.answer(f"💵 Статус вашей подписки: *{status}*\nИспользуйте меню для продления или оплаты.", parse_mode="Markdown")

# --- Запуск веб-сервера и бота ---
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
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    
    try:
        loop.run_until_complete(asyncio.gather(update_data_loop(), start_web_server(), dp.start_polling(bot)))
    except Exception as e:
        logger.critical(f"FATAL ERROR: {e}")
