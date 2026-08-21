import os
import logging
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")

# Настройка детализированного логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Импорты модулей проекта
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
from admin_panel import ADMIN_ID, is_admin, get_financial_stats, get_forecast_stats
from languages import LANGUAGES
from config import CITIES
from agreement import WELCOME_TEXT, AGREEMENT_TEXT, welcome_keyboard, agreement_keyboard, legal_disclaimer

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

def main_menu(user_id):
    lang = get_user_lang(user_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang["buttons"]["rates"], callback_data="rates")],
        [InlineKeyboardButton(text=lang["buttons"]["banks"], callback_data="banks")],
        [InlineKeyboardButton(text=lang["buttons"]["city"], callback_data="city")],
        [InlineKeyboardButton(text=lang["buttons"]["forecast_usd"], callback_data="forecast_usd")],
        [InlineKeyboardButton(text=lang["buttons"]["forecast_eur"], callback_data="forecast_eur")],
        [InlineKeyboardButton(text=lang["buttons"]["analysis"], callback_data="analysis")],
        [InlineKeyboardButton(text=lang["buttons"]["subscribe"], callback_data="subscribe")],
        [InlineKeyboardButton(text=lang["buttons"]["referral"], callback_data="referral")],
        [InlineKeyboardButton(text=lang["buttons"]["support"], callback_data="support")],
        [InlineKeyboardButton(text=lang["buttons"]["profile"], callback_data="profile")],
        [InlineKeyboardButton(text=lang["buttons"]["change_lang"], callback_data="change_lang")],
        [InlineKeyboardButton(text=lang["buttons"]["agreement"], callback_data="agreement")]
    ])

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
# ФОНОВЫЕ ПРОЦЕССЫ И СИСТЕМНАЯ ЗАЩИТА
# ============================================================

async def update_data():
    global CACHE_DATA, LAST_UPDATE
    while True:
        try:
            await parser.get_nbrb_rates()
            for city in CITIES:
                await parser.get_bank_rates_for_city(city)
            forex = await parser.get_forex_data()
            CACHE_DATA = {"nbrb": parser.data, "banks": parser.banks_data, "forex": forex}
            LAST_UPDATE = datetime.now()
            logging.info("✅ Данные успешно обновлены для всех городов")
        except Exception as e:
            logging.error(f"❌ Ошибка в фоновом обновлении данных: {e}")
        await asyncio.sleep(3600)

async def check_spam(user_id):
    now = datetime.now()
    last = USER_LAST_MESSAGE.get(user_id)
    # Использование .total_seconds() предотвращает баги при длительных сессиях
    if last and (now - last).total_seconds() < 3:
        return True
    USER_LAST_MESSAGE[user_id] = now
    return False

def check_subscription(func):
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        status = get_subscription_status(user_id)
        if status == "expired":
            msg = (
                "⏳ Ваша подписка истекла.\n"
                "Оплатите доступ через ЕРИП.\n"
                "После оплаты отправьте команду /confirm <код>"
            )
            if isinstance(event, types.CallbackQuery):
                await event.answer("⏳ Подписка истекла!", show_alert=True)
                await event.message.edit_text(msg, reply_markup=main_menu(user_id))
            else:
                await event.answer(msg, reply_markup=main_menu(user_id))
            return
        return await func(event, *args, **kwargs)
    return wrapper

# ============================================================
# РЕГИСТРАЦИЯ И СТАРТ
# ============================================================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or "пользователь"
    
    user = db.get_user(user_id)
    
    if user and db.has_accepted_agreement(user_id):
        await message.answer(
            f"🤖 *С возвращением, {first_name}!*\n\nВыберите действие:",
            reply_markup=main_menu(user_id),
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

@dp.callback_query(lambda c: c.data == "show_languages")
async def show_languages_from_welcome(callback: types.CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇧🇾 Беларуская", callback_data="lang_be")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇵🇱 Polski", callback_data="lang_pl")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton(text="🇱🇹 Lietuvių", callback_data="lang_lt")]
    ])
    await callback.message.edit_text(
        "🌍 *Выберите язык / Choose language:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    
    if lang_code in LANGUAGES:
        db.set_language(user_id, lang_code)
        await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang_code]['name']}")
        
        if db.has_accepted_agreement(user_id):
            await callback.message.edit_text(
                "🤖 *Главное меню:*",
                reply_markup=main_menu(user_id),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                AGREEMENT_TEXT,
                reply_markup=agreement_keyboard(),
                parse_mode="Markdown"
            )
    else:
        await callback.answer("❌ Неверный язык", show_alert=True)

@dp.callback_query(lambda c: c.data == "accept_agreement")
async def accept_agreement(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    db.accept_agreement(user_id)
    await callback.answer("✅ Соглашение принято!")
    await callback.message.edit_text(
        "🤖 *Добро пожаловать в BYN Super Investor Bot!*\n\nВыберите действие:",
        reply_markup=main_menu(user_id),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "decline_agreement")
async def decline_agreement(callback: types.CallbackQuery):
    await callback.answer("❌ Вы отказались от соглашения.")
    await callback.message.edit_text(
        "❌ Вы отказались от условий использования.\n\nДля возобновления введите /start",
        parse_mode="Markdown"
    )

# ============================================================
# ОСНОВНЫЕ КОМАНДЫ И ИНТЕРАКТИВ
# ============================================================

@dp.message(Command("agreement"))
async def show_agreement_command(message: types.Message):
    await message.answer(AGREEMENT_TEXT, parse_mode="Markdown", reply_markup=agreement_keyboard())

@dp.message(Command("city"))
async def select_city_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=city, callback_data=f"city_{city}")] for city in CITIES
    ])
    await message.answer("🌍 *Выберите город:*", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "city")
async def select_city_callback(callback: types.CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=city, callback_data=f"city_{city}")] for city in CITIES
    ])
    await callback.message.edit_text("🌍 *Выберите город:*", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("city_"))
async def set_city(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    city = callback.data.replace("city_", "")
    if city in CITIES:
        db.set_city(user_id, city)
        await callback.answer(f"✅ Город изменён на {city}")
        await callback.message.edit_text(
            f"✅ Выбран город: *{city}*",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
    else:
        await callback.answer("❌ Город не найден", show_alert=True)

@dp.callback_query(lambda c: c.data == "banks")
async def get_banks_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    city = get_user_city(user_id)
    
    try:
        banks = CACHE_DATA.get("banks", {}).get(city, {})
        offline = banks.get("offline", [])
        online = banks.get("online", [])
        
        if not offline and not online:
            await callback.message.edit_text(f"⏳ Данные для {city} загружаются...", reply_markup=main_menu(user_id))
            return
        
        text = f"🏦 *ТОП-10 банков ({city})*\n" + "═" * 30 + "\n\n"
        if online:
            text += "📱 *ОНЛАЙН*\n"
            for i, b in enumerate(online[:5], 1):
                text += f"{i}. {b['bank']} — USD: {b['usd_buy']:.4f}/{b['usd_sell']:.4f}\n"
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    except Exception:
        await callback.message.edit_text(f"⚠️ Ошибка получения данных для {city}", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "rates")
async def get_rates(callback: types.CallbackQuery):
    await callback.answer()
    nbrb = CACHE_DATA.get('nbrb', {})
    text = f"📊 *Курсы НБРБ*\n🇺🇸 USD: {nbrb.get('usd', {}).get('nbrb', '—')}\n🇪🇺 EUR: {nbrb.get('eur', {}).get('nbrb', '—')}"
    if LAST_UPDATE:
        text += f"\n🕒 Обновлено: {LAST_UPDATE.strftime('%d.%m.%Y %H:%M')}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "forecast_usd")
@check_subscription
async def forecast_usd(callback: types.CallbackQuery):
    await callback.answer()
    city = get_user_city(callback.from_user.id)
    all_banks = sum(CACHE_DATA.get("banks", {}).get(city, {}).values(), [])
    forecast = await ai.generate_forecast("USD", 3.0, [2.95, 2.97, 3.0], all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "forecast_eur")
@check_subscription
async def forecast_eur(callback: types.CallbackQuery):
    await callback.answer()
    city = get_user_city(callback.from_user.id)
    all_banks = sum(CACHE_DATA.get("banks", {}).get(city, {}).values(), [])
    forecast = await ai.generate_forecast("EUR", 3.45, [3.40, 3.42, 3.45], all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "analysis")
@check_subscription
async def analysis(callback: types.CallbackQuery):
    await callback.answer()
    forex = CACHE_DATA.get("forex", {})
    text = f"📈 *Анализ рынка*\n🇷🇺 USD/RUB: {forex.get('usd_rub', '—')}\n🌍 DXY: {forex.get('dxy', '—')}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "subscribe")
@dp.message(Command("subscribe"))
async def subscribe_handler(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    payment = generate_erip_payment(user_id)
    text = f"💳 *Оформление подписки*\n💰 Сумма: {payment['amount']}\n🔗 Ссылка: {payment['erip_link']}\n\nПосле оплаты: `/confirm <код>`"
    
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код операции: `/confirm ERIP0001`", parse_mode="Markdown")
        return
    code = args[1].strip()
    if db.add_pending_payment(message.from_user.id, code, "29.90 BYN"):
        await bot.send_message(ADMIN_ID, f"💳 *Новый платёж!*\n👤 ID: {message.from_user.id}\n🔑 Код: `{code}`\n\n✅ `/approve {code}`", parse_mode="Markdown")
        await message.answer("✅ Платёж сохранён! Ожидайте подтверждения.", reply_markup=main_menu(message.from_user.id))

@dp.message(Command("approve"))
async def approve_payment(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return
    code = args[1].strip()
    user_id = db.approve_payment(code)
    if user_id:
        sub_end = get_subscription_end_date()
        db.update_user(user_id, {"status": "active", "subscription_end": sub_end})
        await bot.send_message(user_id, f"✅ Подписка активирована до {sub_end}!")
        await message.answer(f"✅ Успешно активирован пользователь {user_id}")

@dp.callback_query(lambda c: c.data == "profile")
@dp.message(Command("profile"))
async def profile_handler(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    user = db.get_user(user_id)
    status = get_subscription_status(user_id)
    text = f"📊 *Профиль*\n👤 Имя: {user.get('first_name')}\n📌 Статус: {status}"
    
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "referral")
@dp.message(Command("referral"))
async def referral_handler(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    link = f"https://t.me/byn_investor_bot?start=ref_{user_id}"
    text = f"👥 *Реферальная программа*\n🔗 Ссылка:\n`{link}`"
    
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "support")
@dp.message(Command("support"))
async def support_handler(event: types.Message | types.CallbackQuery):
    text = "🤖 *Консультант*\nЗадайте ваш вопрос, и я помогу."
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(event.from_user.id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(event.from_user.id))

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    args = message.text.split()
    
    if len(args) > 1 and args[1] == "users":
        users = db.data.get("users", [])[:20]
        text = "👥 *Пользователи:*\n" + "\n".join([f"• ID: {u.get('id')}" for u in users])
        await message.answer(text, parse_mode="Markdown")
        return
        
    finance = get_financial_stats()
    text = f"🔐 *Админ-панель*\n💰 Доход: {finance['total_revenue']} BYN"
    await message.answer(text, parse_mode="Markdown")

@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    if await check_spam(user_id):
        return
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Примите соглашение: /agreement")
        return
        
    from ai_support import AISupport
    ai_support = AISupport()
    response = await ai_support.get_response(message.text)
    # Безопасная отправка без строгого Markdown, исключающая TelegramBadRequest
    await message.answer(response.get("text", "Готово"), reply_markup=main_menu(user_id))

# ============================================================
# МИНИ-ВЕБ-СЕРВЕР ДЛЯ RENDER (УСТРАНЯЕТ "No open ports detected")
# ============================================================

async def handle_ping(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle_ping), web.get("/health", handle_ping)])
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 HTTP-сервер успешно запущен на порту {port}")

# ============================================================
# ТОЧКА ВХОДА
# ============================================================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Бот успешно запущен")
    
    # Синхронный параллельный запуск всех ключевых процессов
    await asyncio.gather(
        update_data(),
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
import os
import logging
import asyncio
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")

# Настройка детализированного логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Импорты модулей проекта
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
from admin_panel import ADMIN_ID, is_admin, get_financial_stats, get_forecast_stats
from languages import LANGUAGES
from config import CITIES
from agreement import WELCOME_TEXT, AGREEMENT_TEXT, welcome_keyboard, agreement_keyboard, legal_disclaimer

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

def main_menu(user_id):
    lang = get_user_lang(user_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang["buttons"]["rates"], callback_data="rates")],
        [InlineKeyboardButton(text=lang["buttons"]["banks"], callback_data="banks")],
        [InlineKeyboardButton(text=lang["buttons"]["city"], callback_data="city")],
        [InlineKeyboardButton(text=lang["buttons"]["forecast_usd"], callback_data="forecast_usd")],
        [InlineKeyboardButton(text=lang["buttons"]["forecast_eur"], callback_data="forecast_eur")],
        [InlineKeyboardButton(text=lang["buttons"]["analysis"], callback_data="analysis")],
        [InlineKeyboardButton(text=lang["buttons"]["subscribe"], callback_data="subscribe")],
        [InlineKeyboardButton(text=lang["buttons"]["referral"], callback_data="referral")],
        [InlineKeyboardButton(text=lang["buttons"]["support"], callback_data="support")],
        [InlineKeyboardButton(text=lang["buttons"]["profile"], callback_data="profile")],
        [InlineKeyboardButton(text=lang["buttons"]["change_lang"], callback_data="change_lang")],
        [InlineKeyboardButton(text=lang["buttons"]["agreement"], callback_data="agreement")]
    ])

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
# ФОНОВЫЕ ПРОЦЕССЫ И СИСТЕМНАЯ ЗАЩИТА
# ============================================================

async def update_data():
    global CACHE_DATA, LAST_UPDATE
    while True:
        try:
            await parser.get_nbrb_rates()
            for city in CITIES:
                await parser.get_bank_rates_for_city(city)
            forex = await parser.get_forex_data()
            CACHE_DATA = {"nbrb": parser.data, "banks": parser.banks_data, "forex": forex}
            LAST_UPDATE = datetime.now()
            logging.info("✅ Данные успешно обновлены для всех городов")
        except Exception as e:
            logging.error(f"❌ Ошибка в фоновом обновлении данных: {e}")
        await asyncio.sleep(3600)

async def check_spam(user_id):
    now = datetime.now()
    last = USER_LAST_MESSAGE.get(user_id)
    # Использование .total_seconds() предотвращает баги при длительных сессиях
    if last and (now - last).total_seconds() < 3:
        return True
    USER_LAST_MESSAGE[user_id] = now
    return False

def check_subscription(func):
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        status = get_subscription_status(user_id)
        if status == "expired":
            msg = (
                "⏳ Ваша подписка истекла.\n"
                "Оплатите доступ через ЕРИП.\n"
                "После оплаты отправьте команду /confirm <код>"
            )
            if isinstance(event, types.CallbackQuery):
                await event.answer("⏳ Подписка истекла!", show_alert=True)
                await event.message.edit_text(msg, reply_markup=main_menu(user_id))
            else:
                await event.answer(msg, reply_markup=main_menu(user_id))
            return
        return await func(event, *args, **kwargs)
    return wrapper

# ============================================================
# РЕГИСТРАЦИЯ И СТАРТ
# ============================================================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or "пользователь"
    
    user = db.get_user(user_id)
    
    if user and db.has_accepted_agreement(user_id):
        await message.answer(
            f"🤖 *С возвращением, {first_name}!*\n\nВыберите действие:",
            reply_markup=main_menu(user_id),
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

@dp.callback_query(lambda c: c.data == "show_languages")
async def show_languages_from_welcome(callback: types.CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇧🇾 Беларуская", callback_data="lang_be")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇵🇱 Polski", callback_data="lang_pl")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton(text="🇱🇹 Lietuvių", callback_data="lang_lt")]
    ])
    await callback.message.edit_text(
        "🌍 *Выберите язык / Choose language:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    
    if lang_code in LANGUAGES:
        db.set_language(user_id, lang_code)
        await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang_code]['name']}")
        
        if db.has_accepted_agreement(user_id):
            await callback.message.edit_text(
                "🤖 *Главное меню:*",
                reply_markup=main_menu(user_id),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                AGREEMENT_TEXT,
                reply_markup=agreement_keyboard(),
                parse_mode="Markdown"
            )
    else:
        await callback.answer("❌ Неверный язык", show_alert=True)

@dp.callback_query(lambda c: c.data == "accept_agreement")
async def accept_agreement(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    db.accept_agreement(user_id)
    await callback.answer("✅ Соглашение принято!")
    await callback.message.edit_text(
        "🤖 *Добро пожаловать в BYN Super Investor Bot!*\n\nВыберите действие:",
        reply_markup=main_menu(user_id),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "decline_agreement")
async def decline_agreement(callback: types.CallbackQuery):
    await callback.answer("❌ Вы отказались от соглашения.")
    await callback.message.edit_text(
        "❌ Вы отказались от условий использования.\n\nДля возобновления введите /start",
        parse_mode="Markdown"
    )

# ============================================================
# ОСНОВНЫЕ КОМАНДЫ И ИНТЕРАКТИВ
# ============================================================

@dp.message(Command("agreement"))
async def show_agreement_command(message: types.Message):
    await message.answer(AGREEMENT_TEXT, parse_mode="Markdown", reply_markup=agreement_keyboard())

@dp.message(Command("city"))
async def select_city_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=city, callback_data=f"city_{city}")] for city in CITIES
    ])
    await message.answer("🌍 *Выберите город:*", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "city")
async def select_city_callback(callback: types.CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=city, callback_data=f"city_{city}")] for city in CITIES
    ])
    await callback.message.edit_text("🌍 *Выберите город:*", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("city_"))
async def set_city(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    city = callback.data.replace("city_", "")
    if city in CITIES:
        db.set_city(user_id, city)
        await callback.answer(f"✅ Город изменён на {city}")
        await callback.message.edit_text(
            f"✅ Выбран город: *{city}*",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
    else:
        await callback.answer("❌ Город не найден", show_alert=True)

@dp.callback_query(lambda c: c.data == "banks")
async def get_banks_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    city = get_user_city(user_id)
    
    try:
        banks = CACHE_DATA.get("banks", {}).get(city, {})
        offline = banks.get("offline", [])
        online = banks.get("online", [])
        
        if not offline and not online:
            await callback.message.edit_text(f"⏳ Данные для {city} загружаются...", reply_markup=main_menu(user_id))
            return
        
        text = f"🏦 *ТОП-10 банков ({city})*\n" + "═" * 30 + "\n\n"
        if online:
            text += "📱 *ОНЛАЙН*\n"
            for i, b in enumerate(online[:5], 1):
                text += f"{i}. {b['bank']} — USD: {b['usd_buy']:.4f}/{b['usd_sell']:.4f}\n"
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    except Exception:
        await callback.message.edit_text(f"⚠️ Ошибка получения данных для {city}", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "rates")
async def get_rates(callback: types.CallbackQuery):
    await callback.answer()
    nbrb = CACHE_DATA.get('nbrb', {})
    text = f"📊 *Курсы НБРБ*\n🇺🇸 USD: {nbrb.get('usd', {}).get('nbrb', '—')}\n🇪🇺 EUR: {nbrb.get('eur', {}).get('nbrb', '—')}"
    if LAST_UPDATE:
        text += f"\n🕒 Обновлено: {LAST_UPDATE.strftime('%d.%m.%Y %H:%M')}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "forecast_usd")
@check_subscription
async def forecast_usd(callback: types.CallbackQuery):
    await callback.answer()
    city = get_user_city(callback.from_user.id)
    all_banks = sum(CACHE_DATA.get("banks", {}).get(city, {}).values(), [])
    forecast = await ai.generate_forecast("USD", 3.0, [2.95, 2.97, 3.0], all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "forecast_eur")
@check_subscription
async def forecast_eur(callback: types.CallbackQuery):
    await callback.answer()
    city = get_user_city(callback.from_user.id)
    all_banks = sum(CACHE_DATA.get("banks", {}).get(city, {}).values(), [])
    forecast = await ai.generate_forecast("EUR", 3.45, [3.40, 3.42, 3.45], all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "analysis")
@check_subscription
async def analysis(callback: types.CallbackQuery):
    await callback.answer()
    forex = CACHE_DATA.get("forex", {})
    text = f"📈 *Анализ рынка*\n🇷🇺 USD/RUB: {forex.get('usd_rub', '—')}\n🌍 DXY: {forex.get('dxy', '—')}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "subscribe")
@dp.message(Command("subscribe"))
async def subscribe_handler(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    payment = generate_erip_payment(user_id)
    text = f"💳 *Оформление подписки*\n💰 Сумма: {payment['amount']}\n🔗 Ссылка: {payment['erip_link']}\n\nПосле оплаты: `/confirm <код>`"
    
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код операции: `/confirm ERIP0001`", parse_mode="Markdown")
        return
    code = args[1].strip()
    if db.add_pending_payment(message.from_user.id, code, "29.90 BYN"):
        await bot.send_message(ADMIN_ID, f"💳 *Новый платёж!*\n👤 ID: {message.from_user.id}\n🔑 Код: `{code}`\n\n✅ `/approve {code}`", parse_mode="Markdown")
        await message.answer("✅ Платёж сохранён! Ожидайте подтверждения.", reply_markup=main_menu(message.from_user.id))

@dp.message(Command("approve"))
async def approve_payment(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return
    code = args[1].strip()
    user_id = db.approve_payment(code)
    if user_id:
        sub_end = get_subscription_end_date()
        db.update_user(user_id, {"status": "active", "subscription_end": sub_end})
        await bot.send_message(user_id, f"✅ Подписка активирована до {sub_end}!")
        await message.answer(f"✅ Успешно активирован пользователь {user_id}")

@dp.callback_query(lambda c: c.data == "profile")
@dp.message(Command("profile"))
async def profile_handler(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    user = db.get_user(user_id)
    status = get_subscription_status(user_id)
    text = f"📊 *Профиль*\n👤 Имя: {user.get('first_name')}\n📌 Статус: {status}"
    
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "referral")
@dp.message(Command("referral"))
async def referral_handler(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    link = f"https://t.me/byn_investor_bot?start=ref_{user_id}"
    text = f"👥 *Реферальная программа*\n🔗 Ссылка:\n`{link}`"
    
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "support")
@dp.message(Command("support"))
async def support_handler(event: types.Message | types.CallbackQuery):
    text = "🤖 *Консультант*\nЗадайте ваш вопрос, и я помогу."
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(event.from_user.id))
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=main_menu(event.from_user.id))

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    args = message.text.split()
    
    if len(args) > 1 and args[1] == "users":
        users = db.data.get("users", [])[:20]
        text = "👥 *Пользователи:*\n" + "\n".join([f"• ID: {u.get('id')}" for u in users])
        await message.answer(text, parse_mode="Markdown")
        return
        
    finance = get_financial_stats()
    text = f"🔐 *Админ-панель*\n💰 Доход: {finance['total_revenue']} BYN"
    await message.answer(text, parse_mode="Markdown")

@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    if await check_spam(user_id):
        return
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Примите соглашение: /agreement")
        return
        
    from ai_support import AISupport
    ai_support = AISupport()
    response = await ai_support.get_response(message.text)
    # Безопасная отправка без строгого Markdown, исключающая TelegramBadRequest
    await message.answer(response.get("text", "Готово"), reply_markup=main_menu(user_id))

# ============================================================
# МИНИ-ВЕБ-СЕРВЕР ДЛЯ RENDER (УСТРАНЯЕТ "No open ports detected")
# ============================================================

async def handle_ping(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle_ping), web.get("/health", handle_ping)])
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 HTTP-сервер успешно запущен на порту {port}")

# ============================================================
# ТОЧКА ВХОДА
# ============================================================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Бот успешно запущен")
    
    # Синхронный параллельный запуск всех ключевых процессов
    await asyncio.gather(
        update_data(),
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
