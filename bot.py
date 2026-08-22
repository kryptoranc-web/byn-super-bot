import os
import logging
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Критическая ошибка: BOT_TOKEN не найден в переменных окружения!")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("BYN-Super-Bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= IMPORTS FROM PROJECT MODULES =================
from parser import CurrencyParser
from analyzer import TechnicalAnalyzer
from ai_forecast import AIForecast
from users_db import UserDB
from subscription import (
    get_subscription_status, 
    get_subscription_end_date, 
    get_trial_end_date, 
    TRIAL_DAYS, 
    is_valid_referral
)
from payments import generate_erip_payment
from languages import LANGUAGES
from config import CITIES
from agreement import WELCOME_TEXT, AGREEMENT_TEXT, welcome_keyboard, agreement_keyboard, legal_disclaimer

# Импортируем из нашей админ-панели
from admin_panel import admin_router, is_admin, get_admin_reply_keyboard, check_user_access, ADMIN_ID

# Подключаем роутер админки
dp.include_router(admin_router)

parser = CurrencyParser()
analyzer = TechnicalAnalyzer()
ai = AIForecast()
db = UserDB()

CACHE_DATA = {}
LAST_UPDATE = None
USER_LAST_MESSAGE = {}

def get_user_lang(user_id):
    lang_code = db.get_language(user_id)
    return LANGUAGES.get(lang_code, LANGUAGES["ru"])

def get_user_city(user_id):
    city = db.get_city(user_id)
    return city if city in CITIES else "Минск"

def get_user_reply_keyboard() -> ReplyKeyboardMarkup:
    """Эргономичное и понятное меню для обычных клиентов."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🏙 Выбрать город"),
                KeyboardButton(text="📊 Анализ рынка")
            ],
            [
                KeyboardButton(text="🤖 AI-Прогноз USD"),
                KeyboardButton(text="🤖 AI-Прогноз EUR")
            ],
            [
                KeyboardButton(text="💳 Подписка"),
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="👥 Рефералы")
            ],
            [
                KeyboardButton(text="🤖 Поддержка"),
                KeyboardButton(text="📄 Соглашение")
            ]
        ],
        resize_keyboard=True
    )

# ============================================================
# ФОРМАТИРОВАНИЕ ПРОГНОЗА
# ============================================================

def format_forecast(forecast):
    if not forecast:
        return "⚠️ Ошибка: данные прогноза отсутствуют."
    
    currency = forecast.get("currency", "USD")
    preds = forecast.get("predictions", {})
    levels = forecast.get("levels", {})
    votes = forecast.get("votes", {})
    strategy = forecast.get("strategy", {})
    sources = forecast.get("sources", [])
    
    text = f"🤖 *СУПЕР-ПРОГНОЗ {currency}/BYN*\n"
    text += "═" * 35 + "\n\n"
    
    text += "🎯 *ЧТО ДЕЛАТЬ ПРЯМО СЕЙЧАС:*\n"
    
    rec = forecast.get('recommendation', 'ДЕРЖАТЬ ⏳')
    if rec in ["ПОКУПАТЬ ✅", "ПРОДАВАТЬ ❌"]:
        action_text = "✅ ПОКУПАТЬ" if "ПОКУПАТЬ" in rec else "❌ ПРОДАВАТЬ"
        text += f"{action_text} {currency}\n"
        bank = strategy.get('bank')
        if bank:
            text += f"🏦 Лучший банк: {bank.get('name', '—')} ({bank.get('type', '—')})\n"
            text += f"💱 Курс: {bank.get('rate', '—')} BYN\n"
        text += f"📈 Цель: {strategy.get('exit_price', '—')} BYN (через {strategy.get('hold_days', '—')} дней)\n"
        text += f"💰 Прибыль: +{strategy.get('expected_profit', '—')}%\n"
    else:
        text += "⏳ ДЕРЖАТЬ — рынок не даёт чёткого сигнала\n"
        text += "Рекомендуем воздержаться от сделок.\n"
    
    text += "\n" + "═" * 35 + "\n📊 *ПРОГНОЗ И ТРЕНД*\n" + "═" * 35 + "\n\n"
    text += f"📌 *Текущая ситуация:*\n• Курс НБРБ: {forecast.get('current_rate', '—')}\n"
    
    rsi = forecast.get('rsi', 50)
    if rsi > 70:
        text += f"• RSI: {rsi} (перекупленность 🔴 — сигнал к продаже)\n"
    elif rsi < 30:
        text += f"• RSI: {rsi} (перепроданность 🟢 — сигнал к покупке)\n"
    else:
        text += f"• RSI: {rsi} (нейтральный 🟡)\n"
    
    text += f"• Тренд: {forecast.get('trend', '—')}\n"
    text += f"• Сезонность: {forecast.get('seasonal_impact', '—')}\n\n"
    
    text += "📅 *Прогноз цен:*\n"
    current = forecast.get('current_rate', 0)
    week = preds.get('week', current)
    month = preds.get('month', week)
    quarter = preds.get('quarter', month)
    
    text += f"• Через неделю: {week} {'↑' if week > current else '↓' if week < current else '—'}\n"
    text += f"• Через месяц: {month} {'↑' if month > week else '↓' if month < week else '—'}\n"
    text += f"• Через 3 месяца: {quarter} {'↑' if quarter > month else '↓' if quarter < month else '—'}\n\n"
    
    text += f"📊 *Уровни:*\n🛡️ Поддержка: {levels.get('support', '—')}\n⚔️ Сопротивление: {levels.get('resistance', '—')}\n\n"
    
    text += f"🗳️ *Голосование 10 AI:*\n"
    text += f"• ПОКУПАТЬ ✅: {votes.get('ПОКУПАТЬ ✅', 0)}\n"
    text += f"• ПРОДАВАТЬ ❌: {votes.get('ПРОДАВАТЬ ❌', 0)}\n"
    text += f"• ДЕРЖАТЬ ⏳: {votes.get('ДЕРЖАТЬ ⏳', 0)}\n"
    text += f"📊 Консенсус: {forecast.get('consensus', '—')}\n\n"
    
    text += "═" * 35 + "\n📎 *ИСТОЧНИКИ ДАННЫХ*\n" + "═" * 35 + "\n"
    for source in sources[:4]:
        text += f"• {source.split('—')[0].strip()}\n"
    text += "\n" + legal_disclaimer()
    return text

# ============================================================
# ФОНОВЫЕ ПРОЦЕССЫ И ЗАЩИТА
# ============================================================

async def update_data():
    """Фоновый сбор актуальных курсов валют и данных банков."""
    global CACHE_DATA, LAST_UPDATE
    while True:
        try:
            await parser.get_nbrb_rates()
            for city in CITIES:
                await parser.get_bank_rates_for_city(city)
            forex = await parser.get_forex_data()
            CACHE_DATA = {"nbrb": parser.data, "banks": parser.banks_data, "forex": forex}
            LAST_UPDATE = datetime.now()
            logger.info("✅ Данные успешно обновлены в фоне для всех городов")
        except Exception as e:
            logger.error(f"❌ Ошибка в фоновом обновлении данных: {e}")
        await asyncio.sleep(3600)

async def check_spam(user_id):
    """Антиспам защита (интервал 3 секунды)."""
    now = datetime.now()
    last = USER_LAST_MESSAGE.get(user_id)
    if last and (now - last).total_seconds() < 3:
        return True
    USER_LAST_MESSAGE[user_id] = now
    return False

# ============================================================
# СТАРТ И АВТОРИЗАЦИЯ
# ============================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or "пользователь"
    
    if is_admin(user_id):
        kb = get_admin_reply_keyboard()
        greeting = (
            "👑 *Панель управления активирована, Шеф!*\n"
            "Вам доступно эргономичное меню администратора."
        )
        await message.answer(greeting, reply_markup=kb, parse_mode="Markdown")
        return

    user = db.get_user(user_id)
    if user and db.has_accepted_agreement(user_id):
        kb = get_user_reply_keyboard()
        await message.answer(
            f"🤖 *С возвращением, {first_name}!*\n\nВыберите действие в меню ниже:",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return
    
    args = message.text.split()
    referral_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referral_id = int(args[1].split("_")[1])
        except ValueError:
            pass
    
    if not user:
        new_user = {
            "id": user_id, "username": username, "first_name": first_name,
            "status": "trial", "trial_start": datetime.now().isoformat(),
            "trial_end": get_trial_end_date(), "subscription_end": None,
            "bonus_days": 0, "referrals": [], "referred_by": referral_id,
            "payment_history": [], "forecast_history": [], "is_blocked": False,
            "language": "ru", "city": "Минск", "agreement_accepted": False
        }
        db.add_user(new_user)
        
        if referral_id and is_valid_referral(referral_id, user_id):
            db.update_user(user_id, {"trial_end": (datetime.now() + timedelta(days=TRIAL_DAYS + 3)).isoformat()})
            db.add_referral(referral_id, user_id)
            try:
                await bot.send_message(referral_id, f"🎉 Ваш друг @{username} зарегистрировался!")
            except Exception:
                pass
    
    await message.answer(WELCOME_TEXT, parse_mode="Markdown", reply_markup=welcome_keyboard())

# ============================================================
# ОБРАБОТЧИК КНОПОК ПОЛЬЗОВАТЕЛЯ (ТЕКСТ И CALLBACK)
# ============================================================

@dp.message(F.text == "🏙 Выбрать город")
@dp.callback_query(lambda c: c.data == "city")
async def select_city_handler(event: types.Message | types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=city, callback_data=f"city_{city}")] for city in CITIES
    ])
    text = "🌍 *Выберите ваш город для анализа банковских курсов:*"
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("city_"))
async def set_city_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    city = callback.data.replace("city_", "")
    if city in CITIES:
        db.set_city(user_id, city)
        await callback.answer(f"✅ Город изменён на {city}")
        await callback.message.edit_text(
            f"✅ Успешно выбран город: *{city}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
            ])
        )
    else:
        await callback.answer("❌ Город не найден", show_alert=True)

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🤖 *Главное меню:*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Курсы НБРБ", callback_data="rates")],
            [InlineKeyboardButton(text="🏦 Банки", callback_data="banks")]
        ]),
        parse_mode="Markdown"
    )

@dp.message(F.text == "📊 Анализ рынка")
async def market_analysis_handler(message: types.Message):
    user_id = message.from_user.id
    if not check_user_access(user_id):
        await message.answer("⏳ *Подписка истекла!* Оформите продление через раздел «Подписка».", parse_mode="Markdown")
        return
    
    forex = CACHE_DATA.get("forex", {})
    text = f"📈 *Анализ рынка*\n🇷🇺 USD/RUB: {forex.get('usd_rub', '—')}\n🌍 DXY: {forex.get('dxy', '—')}"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_({"🤖 AI-Прогноз USD", "🤖 AI-Прогноз EUR"}))
async def ai_forecast_handler(message: types.Message):
    user_id = message.from_user.id
    if not check_user_access(user_id):
        await message.answer("⏳ *Подписка истекла!* Доступ к прогнозам заблокирован.", parse_mode="Markdown")
        return
    
    currency = "USD" if "USD" in message.text else "EUR"
    base_rate = 3.0 if currency == "USD" else 3.45
    city = get_user_city(user_id)
    all_banks = sum(CACHE_DATA.get("banks", {}).get(city, {}).values(), [])
    
    forecast = await ai.generate_forecast(currency, base_rate, [base_rate-0.05, base_rate-0.02, base_rate], all_banks)
    await message.answer(format_forecast(forecast), parse_mode="Markdown")

@dp.message(F.text == "💳 Подписка")
@dp.message(Command("subscribe"))
async def subscribe_handler(message: types.Message):
    user_id = message.from_user.id
    payment = generate_erip_payment(user_id)
    text = (
        f"💳 *Оформление подписки*\n\n"
        f"💰 Сумма к оплате: *{payment['amount']}*\n"
        f"🔗 Инфо/Ссылка ЕРИП: {payment['erip_link']}\n\n"
        f"После оплаты отправьте подтверждение:\n`/confirm <ваш_код_операции>`"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код операции: `/confirm ERIP0001`", parse_mode="Markdown")
        return
    code = args[1].strip()
    if db.add_pending_payment(message.from_user.id, code, "29.90 BYN"):
        try:
            await bot.send_message(
                ADMIN_ID, 
                f"💳 *Новый платёж на проверку!*\n👤 ID: {message.from_user.id}\n🔑 Код: `{code}`", 
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await message.answer("✅ Платёж отправлен на проверку администратору. Ожидайте активации!", parse_mode="Markdown")

@dp.message(F.text == "👤 Профиль")
@dp.message(Command("profile"))
async def profile_handler(message: types.Message):
    user_id = message.from_user.id
    user = db.get_user(user_id) or {}
    status = get_subscription_status(user_id)
    text = (
        f"📊 *Ваш профиль*\n\n"
        f"👤 Имя: {user.get('first_name', 'Клиент')}\n"
        f"📌 Статус подписки: *{status}*\n"
        f"🏙 Город: {get_user_city(user_id)}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "👥 Рефералы")
@dp.message(Command("referral"))
async def referral_handler(message: types.Message):
    user_id = message.from_user.id
    link = f"https://t.me/byn_investor_bot?start=ref_{user_id}"
    text = f"👥 *Реферальная программа*\n\nПриглашайте друзей и получайте бонусные дни!\n🔗 Ваша ссылка:\n`{link}`"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🤖 Поддержка")
@dp.message(Command("support"))
async def support_handler(message: types.Message):
    await message.answer("🤖 *Служба поддержки*\nЗадайте ваш вопрос в чате, и наш консультант ответит вам.", parse_mode="Markdown")

@dp.message(F.text == "📄 Соглашение")
@dp.message(Command("agreement"))
async def agreement_handler(message: types.Message):
    await message.answer(AGREEMENT_TEXT, parse_mode="Markdown", reply_markup=agreement_keyboard())

@dp.callback_query(lambda c: c.data == "accept_agreement")
async def accept_agreement(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    db.accept_agreement(user_id)
    await callback.answer("✅ Соглашение принято!")
    kb = get_admin_reply_keyboard() if is_admin(user_id) else get_user_reply_keyboard()
    await callback.message.edit_text(
        "🤖 *Добро пожаловать в торговый бот!*\n\nВыберите действие в меню:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "decline_agreement")
async def decline_agreement(callback: types.CallbackQuery):
    await callback.answer("❌ Вы отказались от соглашения.")
    await callback.message.edit_text("❌ Вы отказались от условий использования. Для возобновления введите /start", parse_mode="Markdown")

# Общий текстовый обработчик (AI-поддержка или антиспам)
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    if await check_spam(user_id):
        return
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Пожалуйста, примите соглашение: /agreement")
        return
        
    try:
        from ai_support import AISupport
        ai_support = AISupport()
        response = await ai_support.get_response(message.text)
        await message.answer(response.get("text", "Готово"))
    except Exception:
        await message.answer("🤖 Сообщение получено. Используйте кнопки меню для навигации.")

# ============================================================
# ВЕБ-СЕРВЕР ДЛЯ RENDER (АНТИ-СОН И ПОРТ 10000)
# ============================================================

async def handle_ping(request):
    return web.Response(text="BYN Super Bot is running and healthy 24/7!", status=200)

async def start_web_server():
    app = web.Application()
    # aiohttp автоматически поддерживает HEAD запросы для add_get
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 HTTP-сервер успешно запущен на порту {port}")

# ============================================================
# ТОЧКА ВХОДА
# ============================================================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Бот успешно инициализирован")
    
    # Параллельный запуск фоновых задач, веб-сервера и пуллинга Telegram
    await asyncio.gather(
        update_data(),
        start_web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот штатно остановлен пользователем.")
