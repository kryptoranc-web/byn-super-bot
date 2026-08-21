import os
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

from parser import CurrencyParser
from analyzer import TechnicalAnalyzer
from ai_forecast import AIForecast
from users_db import UserDB
from subscription import *
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
# ФОРМАТИРОВАНИЕ ПРОГНОЗА (сокращено для экономии места)
# ============================================================

def format_forecast(forecast):
    if not forecast:
        return "⚠️ Ошибка: данные прогноза отсутствуют."
    
    currency = forecast.get("currency", "USD")
    preds = forecast.get("predictions", {})
    levels = forecast.get("levels", {})
    ai_models = forecast.get("ai_models", [])
    sources = forecast.get("sources", [])
    votes = forecast.get("votes", {})
    strategy = forecast.get("strategy", {})
    top_banks = forecast.get("top_banks", {})
    
    text = f"🤖 *СУПЕР-ПРОГНОЗ {currency}/BYN*\n"
    text += "═" * 35 + "\n\n"
    
    text += "🎯 *ЧТО ДЕЛАТЬ ПРЯМО СЕЙЧАС:*\n"
    
    rec = forecast.get('recommendation', 'ДЕРЖАТЬ ⏳')
    if rec == "ПОКУПАТЬ ✅":
        text += "✅ ПОКУПАТЬ " + currency + "\n"
        bank = strategy.get('bank')
        if bank:
            text += f"🏦 Лучший банк: {bank.get('name', '—')} ({bank.get('type', '—')})\n"
            text += f"💱 Курс: {bank.get('rate', '—')} BYN\n"
        text += f"📈 Цель: {strategy.get('exit_price', '—')} BYN (через {strategy.get('hold_days', '—')} дней)\n"
        text += f"💰 Прибыль: +{strategy.get('expected_profit', '—')}%\n"
    elif rec == "ПРОДАВАТЬ ❌":
        text += "❌ ПРОДАВАТЬ " + currency + "\n"
        bank = strategy.get('bank')
        if bank:
            text += f"🏦 Лучший банк: {bank.get('name', '—')} ({bank.get('type', '—')})\n"
            text += f"💱 Курс: {bank.get('rate', '—')} BYN\n"
        text += f"📈 Цель: {strategy.get('exit_price', '—')} BYN (через {strategy.get('hold_days', '—')} дней)\n"
        text += f"💰 Прибыль: +{strategy.get('expected_profit', '—')}%\n"
    else:
        text += "⏳ ДЕРЖАТЬ — рынок не даёт чёткого сигнала\n"
        text += "Рекомендуем воздержаться от сделок.\n"
    
    text += "\n"
    
    text += "═" * 35 + "\n"
    text += "📊 *ПРОГНОЗ И ТРЕНД*\n"
    text += "═" * 35 + "\n\n"
    
    text += "📌 *Текущая ситуация:*\n"
    text += f"• Курс НБРБ: {forecast.get('current_rate', '—')}\n"
    
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
    
    text += "📊 *Уровни:*\n"
    text += f"🛡️ Поддержка (стоп-лосс): {levels.get('support', '—')}\n"
    text += f"⚔️ Сопротивление (цель): {levels.get('resistance', '—')}\n\n"
    
    text += f"🗳️ *Голосование 10 AI:*\n"
    text += f"• ПОКУПАТЬ ✅: {votes.get('ПОКУПАТЬ ✅', 0)} голосов\n"
    text += f"• ПРОДАВАТЬ ❌: {votes.get('ПРОДАВАТЬ ❌', 0)} голосов\n"
    text += f"• ДЕРЖАТЬ ⏳: {votes.get('ДЕРЖАТЬ ⏳', 0)} голосов\n"
    text += f"📊 Консенсус: {forecast.get('consensus', '—')}\n"
    text += f"⚖️ Риск: {forecast.get('risk', '—')}/10 "
    
    risk = forecast.get('risk', 5)
    if risk <= 3:
        text += "(низкий)\n"
    elif risk <= 6:
        text += "(средний)\n"
    else:
        text += "(высокий)\n"
    
    text += "\n"
    
    if strategy and strategy.get("action") != "ДЕРЖАТЬ":
        text += "═" * 35 + "\n"
        text += "💰 *ТОРГОВАЯ СТРАТЕГИЯ (ПОШАГОВО)*\n"
        text += "═" * 35 + "\n\n"
        
        for step in strategy.get('steps', []):
            text += f"{step}\n"
        text += "\n"
    
    text += "═" * 35 + "\n"
    text += "🔬 *ПРОВЕРКА 10 AI-МОДЕЛЕЙ*\n"
    text += "═" * 35 + "\n\n"
    
    for i, ai_model in enumerate(ai_models[:10], 1):
        text += f"{i}. {ai_model['decision']} — {ai_model['reason'][:50]}...\n"
    text += "\n"
    
    text += "═" * 35 + "\n"
    text += "🏦 *СПРАВОЧНО: КУРСЫ БАНКОВ*\n"
    text += "═" * 35 + "\n\n"
    
    if top_banks and top_banks.get("online"):
        text += "📱 *ТОП-5 БАНКОВ (ОНЛАЙН)* — лучшие курсы\n"
        text += "─" * 30 + "\n\n"
        
        for i, bank in enumerate(top_banks.get("online", [])[:5], 1):
            text += f"*{i}. {bank.get('bank', '—')}*\n"
            text += f"💵 USD: {bank.get('usd_buy', 0):.4f} / {bank.get('usd_sell', 0):.4f}  |  Спред: {bank.get('usd_sell', 0) - bank.get('usd_buy', 0):.4f}\n"
            text += f"💶 EUR: {bank.get('eur_buy', 0):.4f} / {bank.get('eur_sell', 0):.4f}  |  Спред: {bank.get('eur_sell', 0) - bank.get('eur_buy', 0):.4f}\n\n"
    
    if top_banks and top_banks.get("offline"):
        text += "🏦 *ТОП-5 БАНКОВ (ОТДЕЛЕНИЯ)*\n"
        text += "─" * 30 + "\n\n"
        
        for i, bank in enumerate(top_banks.get("offline", [])[:5], 1):
            text += f"*{i}. {bank.get('bank', '—')}*\n"
            text += f"📍 {bank.get('address', '—')}\n"
            text += f"💵 USD: {bank.get('usd_buy', 0):.4f} / {bank.get('usd_sell', 0):.4f}  |  Спред: {bank.get('usd_sell', 0) - bank.get('usd_buy', 0):.4f}\n"
            text += f"💶 EUR: {bank.get('eur_buy', 0):.4f} / {bank.get('eur_sell', 0):.4f}  |  Спред: {bank.get('eur_sell', 0) - bank.get('eur_buy', 0):.4f}\n\n"
    
    if top_banks and top_banks.get("best_buy") and top_banks.get("best_sell"):
        text += "⭐ *ЛУЧШИЕ ПРЕДЛОЖЕНИЯ*\n"
        text += "─" * 30 + "\n"
        
        best_buy = top_banks.get("best_buy")
        buy_key = f"{currency.lower()}_buy"
        text += f"🟢 Покупка: {best_buy.get('bank', '—')} ({best_buy.get('type', '—')}) — {best_buy.get(buy_key, '—')}\n"
        
        best_sell = top_banks.get("best_sell")
        sell_key = f"{currency.lower()}_sell"
        text += f"🔴 Продажа: {best_sell.get('bank', '—')} ({best_sell.get('type', '—')}) — {best_sell.get(sell_key, '—')}\n\n"
    
    text += "═" * 35 + "\n"
    text += "📎 *ИСТОЧНИКИ ДАННЫХ*\n"
    text += "═" * 35 + "\n"
    for source in sources[:4]:
        text += f"• {source.split('—')[0].strip()}\n"
    text += "\n"
    
    text += legal_disclaimer()
    return text

# ============================================================
# ФОНОВОЕ ОБНОВЛЕНИЕ ДАННЫХ
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
            logging.info("✅ Данные обновлены для всех городов")
        except Exception as e:
            logging.error(f"❌ Ошибка обновления: {e}")
        await asyncio.sleep(3600)

async def check_spam(user_id):
    now = datetime.now()
    last = USER_LAST_MESSAGE.get(user_id)
    if last and (now - last).seconds < 3:
        return True
    USER_LAST_MESSAGE[user_id] = now
    return False

def check_subscription(func):
    async def wrapper(callback_or_message, *args, **kwargs):
        user_id = callback_or_message.from_user.id
        status = get_subscription_status(user_id)
        if status == "expired":
            await callback_or_message.answer(
                "⏳ Ваша подписка истекла.\n"
                "Оплатите доступ через ЕРИП.\n"
                "После оплаты нажмите /confirm_payment",
                reply_markup=main_menu(user_id)
            )
            return
        return await func(callback_or_message, *args, **kwargs)
    return wrapper

# ============================================================
# КОМАНДА /START — НОВАЯ ВЕРСИЯ С ВЫБОРОМ ЯЗЫКА
# ============================================================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or "пользователь"
    
    user = db.get_user(user_id)
    
    # Если пользователь уже принял соглашение — сразу главное меню
    if user and db.has_accepted_agreement(user_id):
        lang = get_user_lang(user_id)
        await message.answer(
            f"🤖 *С возвращением, {first_name}!*\n\n"
            f"Выберите действие:",
            reply_markup=main_menu(user_id),
            parse_mode="Markdown"
        )
        return
    
    # Проверяем реферала
    args = message.text.split()
    referral_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referral_id = int(args[1].split("_")[1])
        except:
            pass
    
    # Регистрируем нового пользователя
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
            except:
                pass
    
    # Показываем яркое приветствие с выбором языка
    await message.answer(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=welcome_keyboard()
    )

# ============================================================
# ОБРАБОТЧИК ВЫБОРА ЯЗЫКА ИЗ ПРИВЕТСТВИЯ
# ============================================================

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
        "🌍 *Выберите язык / Choose language:*\n\n"
        "После выбора языка вы сможете ознакомиться с условиями использования.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ============================================================
# УСТАНОВКА ЯЗЫКА И ПОКАЗ СОГЛАШЕНИЯ
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    
    if lang_code in LANGUAGES:
        db.set_language(user_id, lang_code)
        await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang_code]['name']}")
        
        # Показываем соглашение на выбранном языке
        lang = get_user_lang(user_id)
        
        # Простой перевод соглашения (для демонстрации)
        if lang_code == "be":
            agreement_text = AGREEMENT_TEXT.replace("Сервис", "Сэрвіс").replace("Пользователь", "Карыстальнік")
        elif lang_code == "en":
            agreement_text = "📋 *TERMS OF USE*\n\nPlease read the terms carefully.\n\nBy clicking 'I accept', you agree to all terms."
        elif lang_code == "pl":
            agreement_text = "📋 *REGULAMIN*\n\nProsimy o zapoznanie się z warunkami.\n\nKlikając 'Akceptuję', zgadzasz się na wszystkie warunki."
        elif lang_code == "ua":
            agreement_text = "📋 *УГОДА КОРИСТУВАЧА*\n\nБудь ласка, ознайомтеся з умовами.\n\nНатискаючи 'Я приймаю', ви погоджуєтеся з усіма умовами."
        elif lang_code == "lt":
            agreement_text = "📋 *NAUDOJIMO SĄLYGOS*\n\nPrašome susipažinti su sąlygomis.\n\nSpustelėdami 'Sutinku', sutinkate su visomis sąlygomis."
        else:
            agreement_text = AGREEMENT_TEXT
        
        await callback.message.edit_text(
            agreement_text,
            parse_mode="Markdown",
            reply_markup=agreement_keyboard()
        )
    else:
        await callback.answer("❌ Неверный язык")

# ============================================================
# ПРИНЯТИЕ СОГЛАШЕНИЯ
# ============================================================

@dp.callback_query(lambda c: c.data == "accept_agreement")
async def accept_agreement(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if db.has_accepted_agreement(user_id):
        await callback.answer("✅ Вы уже приняли соглашение.")
        lang = get_user_lang(user_id)
        await callback.message.edit_text(
            f"🤖 *Добро пожаловать в BYN Super Investor Bot!*\n\n"
            f"Теперь вам доступны все функции:\n"
            f"• 📊 Курсы валют\n"
            f"• 🏦 ТОП-10 банков в вашем городе\n"
            f"• 🤖 AI-прогнозы USD и EUR\n"
            f"• 📈 Анализ рынка\n"
            f"• 👥 Реферальная программа\n"
            f"• 💳 Оформление подписки\n\n"
            f"Выберите действие:",
            reply_markup=main_menu(user_id),
            parse_mode="Markdown"
        )
        return
    
    db.accept_agreement(user_id)
    await callback.answer("✅ Соглашение принято!")
    
    lang = get_user_lang(user_id)
    await callback.message.edit_text(
        f"🤖 *Добро пожаловать в BYN Super Investor Bot!*\n\n"
        f"Теперь вам доступны все функции:\n"
        f"• 📊 Курсы валют\n"
        f"• 🏦 ТОП-10 банков в вашем городе\n"
        f"• 🤖 AI-прогнозы USD и EUR\n"
        f"• 📈 Анализ рынка\n"
        f"• 👥 Реферальная программа\n"
        f"• 💳 Оформление подписки\n\n"
        f"Выберите действие:",
        reply_markup=main_menu(user_id),
        parse_mode="Markdown"
    )

# ============================================================
# ОТКАЗ ОТ СОГЛАШЕНИЯ
# ============================================================

@dp.callback_query(lambda c: c.data == "decline_agreement")
async def decline_agreement(callback: types.CallbackQuery):
    await callback.answer("❌ Вы отказались от соглашения.")
    await callback.message.edit_text(
        "❌ Вы отказались от условий использования.\n\n"
        "Если передумаете, просто напишите /start снова.\n"
        "Мы будем рады видеть вас снова! 😊",
        parse_mode="Markdown"
    )

# ============================================================
# ОСТАЛЬНЫЕ КОМАНДЫ (без изменений)
# ============================================================

@dp.message(Command("agreement"))
async def show_agreement_command(message: types.Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if user and db.has_accepted_agreement(user_id):
        await message.answer(
            "✅ Вы уже приняли соглашение.\n\n"
            "Вы можете перечитать его ниже:",
            parse_mode="Markdown"
        )
    
    await message.answer(
        AGREEMENT_TEXT,
        parse_mode="Markdown",
        reply_markup=agreement_keyboard()
    )

@dp.message(Command("city"))
async def select_city_command(message: types.Message):
    user_id = message.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    for city in CITIES:
        buttons.append(InlineKeyboardButton(text=city, callback_data=f"city_{city}"))
    
    for i in range(0, len(buttons), 3):
        keyboard.inline_keyboard.append(buttons[i:i+3])
    
    await message.answer(
        "🌍 *Выберите город для отображения банков:*\n\n"
        "Бот покажет топ-10 банков в выбранном городе.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "city")
async def select_city_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text(
            "⚠️ Сначала примите соглашение: /agreement",
            reply_markup=main_menu(user_id)
        )
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    for city in CITIES:
        buttons.append(InlineKeyboardButton(text=city, callback_data=f"city_{city}"))
    
    for i in range(0, len(buttons), 3):
        keyboard.inline_keyboard.append(buttons[i:i+3])
    
    await callback.message.edit_text(
        "🌍 *Выберите город для отображения банков:*\n\n"
        "Бот покажет топ-10 банков в выбранном городе.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("city_"))
async def set_city(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    city = callback.data.replace("city_", "")
    
    if city in CITIES:
        db.set_city(user_id, city)
        await callback.answer(f"✅ Город изменён на {city}")
        await callback.message.edit_text(
            f"✅ Город для отображения банков: *{city}*\n\n"
            f"Теперь команда /banks покажет банки в {city}.",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
    else:
        await callback.answer("❌ Город не найден")

@dp.callback_query(lambda c: c.data == "banks")
async def get_banks_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text(
            "⚠️ Сначала примите соглашение: /agreement",
            reply_markup=main_menu(user_id)
        )
        return
    
    city = get_user_city(user_id)
    
    try:
        banks_data = CACHE_DATA.get("banks", {})
        banks = banks_data.get(city, {})
        offline = banks.get("offline", []) if banks else []
        online = banks.get("online", []) if banks else []
        
        if not offline and not online:
            await parser.get_bank_rates_for_city(city)
            banks = parser.banks_data.get(city, {})
            offline = banks.get("offline", []) if banks else []
            online = banks.get("online", []) if banks else []
        
        if not offline and not online:
            await callback.message.edit_text(
                f"⏳ Данные для {city} загружаются...\nПопробуйте через минуту.",
                reply_markup=main_menu(user_id)
            )
            return
        
        text = f"🏦 *ТОП-10 банков {city}*\n"
        text += "═" * 30 + "\n\n"
        
        if online:
            text += "📱 *ОНЛАЙН (лучшие курсы)*\n"
            text += "─" * 25 + "\n"
            for i, bank in enumerate(online[:5], 1):
                text += f"*{i}. {bank['bank']}*\n"
                text += f"💵 USD: {bank['usd_buy']:.4f} / {bank['usd_sell']:.4f}\n"
                text += f"💶 EUR: {bank['eur_buy']:.4f} / {bank['eur_sell']:.4f}\n\n"
        
        if offline:
            text += "🏦 *ОТДЕЛЕНИЯ*\n"
            text += "─" * 25 + "\n"
            for i, bank in enumerate(offline[:5], 1):
                text += f"*{i}. {bank['bank']}*\n"
                text += f"📍 {bank.get('address', '—')}\n"
                text += f"💵 USD: {bank['usd_buy']:.4f} / {bank['usd_sell']:.4f}\n"
                text += f"💶 EUR: {bank['eur_buy']:.4f} / {bank['eur_sell']:.4f}\n\n"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    except Exception as e:
        await callback.message.edit_text(
            f"⚠️ Ошибка получения данных для {city}",
            reply_markup=main_menu(user_id)
        )

@dp.callback_query(lambda c: c.data == "rates")
async def get_rates(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    nbrb_data = CACHE_DATA.get('nbrb', {})
    usd_rate = nbrb_data.get('usd', {}).get('nbrb', '—')
    eur_rate = nbrb_data.get('eur', {}).get('nbrb', '—')
    text = f"📊 *Курсы НБРБ*\n🇺🇸 USD/BYN: {usd_rate}\n🇪🇺 EUR/BYN: {eur_rate}\n"
    if LAST_UPDATE:
        text += f"\n🕒 Обновлено: {LAST_UPDATE.strftime('%d.%m.%Y %H:%M')}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "forecast_usd")
@check_subscription
async def forecast_usd(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    current_rate = CACHE_DATA.get("nbrb", {}).get("usd", {}).get("nbrb", 3.0)
    historical = [2.95, 2.97, 2.98, 2.99, 3.0, 2.99, 2.98, 2.97, 2.96, 2.95]
    
    city = get_user_city(user_id)
    banks_data = CACHE_DATA.get("banks", {}).get(city, {})
    all_banks = banks_data.get("offline", []) + banks_data.get("online", [])
    
    forecast = await ai.generate_forecast("USD", current_rate, historical, all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "forecast_eur")
@check_subscription
async def forecast_eur(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    current_rate = CACHE_DATA.get("nbrb", {}).get("eur", {}).get("nbrb", 3.45)
    historical = [3.40, 3.42, 3.43, 3.44, 3.45, 3.44, 3.43, 3.42, 3.41, 3.40]
    
    city = get_user_city(user_id)
    banks_data = CACHE_DATA.get("banks", {}).get(city, {})
    all_banks = banks_data.get("offline", []) + banks_data.get("online", [])
    
    forecast = await ai.generate_forecast("EUR", current_rate, historical, all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "analysis")
@check_subscription
async def analysis(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    forex = CACHE_DATA.get("forex", {})
    usd_rate = CACHE_DATA.get("nbrb", {}).get("usd", {}).get("nbrb", '—')
    eur_rate = CACHE_DATA.get("nbrb", {}).get("eur", {}).get("nbrb", '—')
    text = (f"📈 *Анализ рынка*\n\n🇺🇸 USD/BYN: {usd_rate}\n🇪🇺 EUR/BYN: {eur_rate}\n🇷🇺 USD/RUB: {forex.get('usd_rub', '—')}\n🌍 DXY: {forex.get('dxy', '—')}\n🛢️ Brent: {forex.get('brent', '—')}\n🇪🇺 EUR/USD: {forex.get('eur_usd', '—')}\n\n💡 *Влияние на курс BYN:*\n• Российский рубль — ключевой фактор\n• Цена нефти влияет на RUB\n• 20-е числа — налоговый период\n• Корреляция с USD/RUB: 0.89")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "subscribe")
async def subscribe_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    payment = generate_erip_payment(user_id)
    text = f"💳 *Оформление подписки*\n\n💳 Номер карты: {payment['receiver_card']}\n🏦 Банк: {payment['receiver_bank']}\n💰 Сумма: {payment['amount']}\n📋 Назначение: {payment['purpose']}\n\n🔗 Ссылка: {payment['erip_link']}\n\nПосле оплаты нажмите /confirm_payment"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("subscribe"))
async def subscribe_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Вы не зарегистрированы. Напишите /start")
        return
    payment = generate_erip_payment(user_id)
    text = f"💳 *Оформление подписки*\n\n💳 Номер карты: {payment['receiver_card']}\n🏦 Банк: {payment['receiver_bank']}\n💰 Сумма: {payment['amount']}\n📋 Назначение: {payment['purpose']}\n\n🔗 Ссылка: {payment['erip_link']}\n\nПосле оплаты нажмите /confirm_payment"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код операции.\nПример: `/confirm ERIP000123456`", parse_mode="Markdown")
        return
    payment_code = args[1].strip()
    if db.add_pending_payment(user_id, payment_code, "29.90 BYN"):
        await bot.send_message(ADMIN_ID, f"💳 *Новый платёж!*\n\n👤 @{message.from_user.username or 'без username'}\n📱 ID: {user_id}\n🔑 Код: `{payment_code}`\n💰 29.90 BYN\n\n✅ `/approve {payment_code}`")
        await message.answer(f"✅ Код `{payment_code}` сохранён! Ожидайте подтверждения.", parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await message.answer("⚠️ Ошибка сохранения платежа.", reply_markup=main_menu(user_id))

@dp.message(Command("approve"))
async def approve_payment(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код операции.\nПример: `/approve ERIP000123456`")
        return
    payment_code = args[1].strip()
    user_id = db.approve_payment(payment_code)
    if not user_id:
        await message.answer(f"❌ Платёж с кодом `{payment_code}` не найден.", parse_mode="Markdown")
        return
    subscription_end = get_subscription_end_date()
    db.update_user(user_id, {"status": "active", "subscription_end": subscription_end})
    await bot.send_message(user_id, f"✅ *Платёж подтверждён!* Подписка активна до {subscription_end}.", parse_mode="Markdown")
    await message.answer(f"✅ Платёж подтверждён! Пользователь {user_id} активирован до {subscription_end}")

@dp.message(Command("profile"))
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    user = db.get_user(user_id)
    if not user:
        await message.answer("Вы не зарегистрированы. Напишите /start")
        return
    status = get_subscription_status(user_id)
    city = get_user_city(user_id)
    text = f"📊 *Ваш профиль*\n\n👤 Имя: {user.get('first_name')}\n🌍 Город: {city}\n📌 Статус: {status}\n"
    if status == "trial":
        text += f"⏳ Пробный период до: {user.get('trial_end')}"
    elif status == "active":
        text += f"✅ Подписка до: {user.get('subscription_end')}"
    else:
        text += "❌ Подписка истекла"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.message.edit_text("Вы не зарегистрированы. Напишите /start", reply_markup=main_menu(user_id))
        return
    
    status = get_subscription_status(user_id)
    city = get_user_city(user_id)
    text = f"📊 *Ваш профиль*\n\n👤 Имя: {user.get('first_name')}\n🌍 Город: {city}\n📌 Статус: {status}\n"
    if status == "trial":
        text += f"⏳ Пробный период до: {user.get('trial_end')}"
    elif status == "active":
        text += f"✅ Подписка до: {user.get('subscription_end')}"
    else:
        text += "❌ Подписка истекла"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("referral"))
async def referral_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    user = db.get_user(user_id)
    if not user:
        await message.answer("Вы не зарегистрированы. Напишите /start")
        return
    referral_link = f"https://t.me/byn_investor_bot?start=ref_{user_id}"
    stats = db.get_referral_stats(user_id)
    text = f"👥 *Реферальная программа*\n\n🔗 *Ваша ссылка:*\n`{referral_link}`\n\n📊 *Статистика:*\n• Приглашено: {stats['total_referrals'] if stats else 0}\n• Активных: {stats['active_referrals'] if stats else 0}\n• Бонусных дней: {stats['bonus_days'] if stats else 0}"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "referral")
async def referral_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.message.edit_text("Вы не зарегистрированы. Напишите /start", reply_markup=main_menu(user_id))
        return
    
    referral_link = f"https://t.me/byn_investor_bot?start=ref_{user_id}"
    stats = db.get_referral_stats(user_id)
    text = f"👥 *Реферальная программа*\n\n🔗 *Ваша ссылка:*\n`{referral_link}`\n\n📊 *Статистика:*\n• Приглашено: {stats['total_referrals'] if stats else 0}\n• Активных: {stats['active_referrals'] if stats else 0}\n• Бонусных дней: {stats['bonus_days'] if stats else 0}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("support"))
async def support_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await message.answer(
        "🤖 *Консультант*\n\nНапишите ваш вопрос. Если я не смогу ответить — переключу на эксперта.",
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@dp.callback_query(lambda c: c.data == "support")
async def support_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    await callback.message.edit_text(
        "🤖 *Консультант*\n\nНапишите ваш вопрос. Если я не смогу ответить — переключу на эксперта.",
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@dp.message(Command("connect"))
async def connect_to_expert(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await bot.send_message(ADMIN_ID, f"🆘 *Запрос на консультацию!*\n\n👤 @{message.from_user.username or 'без username'}\n📱 ID: {user_id}\n\nДля ответа: `/reply {user_id} Ваш ответ`")
    await message.answer("🆘 Запрос передан эксперту. Ожидайте ответа.", reply_markup=main_menu(user_id))

@dp.message(Command("reply"))
async def reply_to_user(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: `/reply <user_id> <текст>`")
        return
    try:
        target_user_id = int(args[1])
        reply_text = args[2]
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    await bot.send_message(target_user_id, f"📩 *Ответ эксперта:*\n\n{reply_text}", parse_mode="Markdown")
    await message.answer(f"✅ Ответ отправлен пользователю {target_user_id}")

@dp.message(Command("lang"))
async def change_language_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇧🇾 Беларуская", callback_data="lang_be")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇵🇱 Polski", callback_data="lang_pl")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton(text="🇱🇹 Lietuvių", callback_data="lang_lt")]
    ])
    await message.answer(
        "🌍 *Выберите язык / Choose language:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "change_lang")
async def show_languages_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
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
async def set_language_from_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    if lang_code in LANGUAGES:
        db.set_language(user_id, lang_code)
        await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang_code]['name']}")
        lang = get_user_lang(user_id)
        await callback.message.edit_text(
            lang["start"],
            reply_markup=main_menu(user_id),
            parse_mode="Markdown"
        )
    else:
        await callback.answer("❌ Неверный язык")

@dp.callback_query(lambda c: c.data == "agreement")
async def agreement_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if user and db.has_accepted_agreement(user_id):
        await callback.message.edit_text(
            "✅ Вы уже приняли соглашение.\n\n"
            "Вы можете перечитать его ниже:",
            parse_mode="Markdown"
        )
    
    await callback.message.edit_text(
        AGREEMENT_TEXT,
        parse_mode="Markdown",
        reply_markup=agreement_keyboard()
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    finance = get_financial_stats()
    forecast = get_forecast_stats()
    text = (f"🔐 *АДМИН-ПАНЕЛЬ*\n\n📊 *ФИНАНСЫ*\n💰 Общий доход: {finance['total_revenue']} BYN\n📈 За месяц: {finance['monthly_revenue']} BYN\n📅 За год: {finance['yearly_revenue']} BYN\n👥 Активных: {finance['active_subscriptions']}\n⏳ Пробный: {finance['trial_users']}\n❌ Просрочено: {finance['expired_users']}\n\n📈 *ПРОГНОЗЫ*\n🎯 Точность: {forecast['accuracy']}%\n🇺🇸 USD: {forecast['usd']['accuracy']}% ({forecast['usd']['total']})\n🇪🇺 EUR: {forecast['eur']['accuracy']}% ({forecast['eur']['total']})")
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("admin users"))
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    users = db.data["users"]
    text = "👥 *СПИСОК ПОЛЬЗОВАТЕЛЕЙ*\n\n"
    for user in users[:20]:
        status = user.get("status", "unknown")
        status_emoji = "✅" if status == "active" else "⏳" if status == "trial" else "❌"
        text += f"{status_emoji} @{user.get('username', 'без username')} | ID: {user.get('id')}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("admin user"))
async def admin_user_detail(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: `/admin user <id>`")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    user = db.get_user(target_id)
    if not user:
        await message.answer("Пользователь не найден.")
        return
    total_paid = sum([float(p.get("amount", 0)) for p in user.get("payment_history", [])])
    total_forecasts = len(user.get("forecast_history", []))
    correct_forecasts = len([f for f in user.get("forecast_history", []) if f.get("actual_result") == "WIN"])
    accuracy = round(correct_forecasts / total_forecasts * 100, 1) if total_forecasts > 0 else 0
    text = (f"👤 *ДЕТАЛИ ПОЛЬЗОВАТЕЛЯ*\n\n📱 ID: {user.get('id')}\n👤 Имя: {user.get('first_name')}\n📌 Статус: {user.get('status')}\n💳 Подписка до: {user.get('subscription_end')}\n💰 Всего оплачено: {total_paid} BYN\n📈 Прогнозов: {total_forecasts} | Точность: {accuracy}%\n\n📋 *ИСТОРИЯ ПЛАТЕЖЕЙ:*")
    for payment in user.get("payment_history", [])[-5:]:
        text += f"\n• {payment.get('date')}: {payment.get('amount')} BYN ({payment.get('status')})"
    await message.answer(text, parse_mode="Markdown")

@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    if await check_spam(user_id):
        return
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    from ai_support import AISupport
    ai_support = AISupport()
    response = await ai_support.get_response(message.text)
    if response.get("escalate"):
        await bot.send_message(
            ADMIN_ID,
            f"🆘 *Вопрос от @{message.from_user.username or 'без username'}*\n📝 {message.text}\n\nДля ответа: `/reply {user_id} Ваш ответ`",
            parse_mode="Markdown"
        )
        await message.answer("🆘 Вопрос передан эксперту. Ожидайте ответа.", reply_markup=main_menu(user_id))
    else:
        await message.answer(response["text"], parse_mode="Markdown", reply_markup=main_menu(user_id))

# ============================================================
# ЗАПУСК БОТА
# ============================================================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Бот запущен")
    asyncio.create_task(update_data())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) import os
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

from parser import CurrencyParser
from analyzer import TechnicalAnalyzer
from ai_forecast import AIForecast
from users_db import UserDB
from subscription import *
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
# ФОРМАТИРОВАНИЕ ПРОГНОЗА (сокращено для экономии места)
# ============================================================

def format_forecast(forecast):
    if not forecast:
        return "⚠️ Ошибка: данные прогноза отсутствуют."
    
    currency = forecast.get("currency", "USD")
    preds = forecast.get("predictions", {})
    levels = forecast.get("levels", {})
    ai_models = forecast.get("ai_models", [])
    sources = forecast.get("sources", [])
    votes = forecast.get("votes", {})
    strategy = forecast.get("strategy", {})
    top_banks = forecast.get("top_banks", {})
    
    text = f"🤖 *СУПЕР-ПРОГНОЗ {currency}/BYN*\n"
    text += "═" * 35 + "\n\n"
    
    text += "🎯 *ЧТО ДЕЛАТЬ ПРЯМО СЕЙЧАС:*\n"
    
    rec = forecast.get('recommendation', 'ДЕРЖАТЬ ⏳')
    if rec == "ПОКУПАТЬ ✅":
        text += "✅ ПОКУПАТЬ " + currency + "\n"
        bank = strategy.get('bank')
        if bank:
            text += f"🏦 Лучший банк: {bank.get('name', '—')} ({bank.get('type', '—')})\n"
            text += f"💱 Курс: {bank.get('rate', '—')} BYN\n"
        text += f"📈 Цель: {strategy.get('exit_price', '—')} BYN (через {strategy.get('hold_days', '—')} дней)\n"
        text += f"💰 Прибыль: +{strategy.get('expected_profit', '—')}%\n"
    elif rec == "ПРОДАВАТЬ ❌":
        text += "❌ ПРОДАВАТЬ " + currency + "\n"
        bank = strategy.get('bank')
        if bank:
            text += f"🏦 Лучший банк: {bank.get('name', '—')} ({bank.get('type', '—')})\n"
            text += f"💱 Курс: {bank.get('rate', '—')} BYN\n"
        text += f"📈 Цель: {strategy.get('exit_price', '—')} BYN (через {strategy.get('hold_days', '—')} дней)\n"
        text += f"💰 Прибыль: +{strategy.get('expected_profit', '—')}%\n"
    else:
        text += "⏳ ДЕРЖАТЬ — рынок не даёт чёткого сигнала\n"
        text += "Рекомендуем воздержаться от сделок.\n"
    
    text += "\n"
    
    text += "═" * 35 + "\n"
    text += "📊 *ПРОГНОЗ И ТРЕНД*\n"
    text += "═" * 35 + "\n\n"
    
    text += "📌 *Текущая ситуация:*\n"
    text += f"• Курс НБРБ: {forecast.get('current_rate', '—')}\n"
    
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
    
    text += "📊 *Уровни:*\n"
    text += f"🛡️ Поддержка (стоп-лосс): {levels.get('support', '—')}\n"
    text += f"⚔️ Сопротивление (цель): {levels.get('resistance', '—')}\n\n"
    
    text += f"🗳️ *Голосование 10 AI:*\n"
    text += f"• ПОКУПАТЬ ✅: {votes.get('ПОКУПАТЬ ✅', 0)} голосов\n"
    text += f"• ПРОДАВАТЬ ❌: {votes.get('ПРОДАВАТЬ ❌', 0)} голосов\n"
    text += f"• ДЕРЖАТЬ ⏳: {votes.get('ДЕРЖАТЬ ⏳', 0)} голосов\n"
    text += f"📊 Консенсус: {forecast.get('consensus', '—')}\n"
    text += f"⚖️ Риск: {forecast.get('risk', '—')}/10 "
    
    risk = forecast.get('risk', 5)
    if risk <= 3:
        text += "(низкий)\n"
    elif risk <= 6:
        text += "(средний)\n"
    else:
        text += "(высокий)\n"
    
    text += "\n"
    
    if strategy and strategy.get("action") != "ДЕРЖАТЬ":
        text += "═" * 35 + "\n"
        text += "💰 *ТОРГОВАЯ СТРАТЕГИЯ (ПОШАГОВО)*\n"
        text += "═" * 35 + "\n\n"
        
        for step in strategy.get('steps', []):
            text += f"{step}\n"
        text += "\n"
    
    text += "═" * 35 + "\n"
    text += "🔬 *ПРОВЕРКА 10 AI-МОДЕЛЕЙ*\n"
    text += "═" * 35 + "\n\n"
    
    for i, ai_model in enumerate(ai_models[:10], 1):
        text += f"{i}. {ai_model['decision']} — {ai_model['reason'][:50]}...\n"
    text += "\n"
    
    text += "═" * 35 + "\n"
    text += "🏦 *СПРАВОЧНО: КУРСЫ БАНКОВ*\n"
    text += "═" * 35 + "\n\n"
    
    if top_banks and top_banks.get("online"):
        text += "📱 *ТОП-5 БАНКОВ (ОНЛАЙН)* — лучшие курсы\n"
        text += "─" * 30 + "\n\n"
        
        for i, bank in enumerate(top_banks.get("online", [])[:5], 1):
            text += f"*{i}. {bank.get('bank', '—')}*\n"
            text += f"💵 USD: {bank.get('usd_buy', 0):.4f} / {bank.get('usd_sell', 0):.4f}  |  Спред: {bank.get('usd_sell', 0) - bank.get('usd_buy', 0):.4f}\n"
            text += f"💶 EUR: {bank.get('eur_buy', 0):.4f} / {bank.get('eur_sell', 0):.4f}  |  Спред: {bank.get('eur_sell', 0) - bank.get('eur_buy', 0):.4f}\n\n"
    
    if top_banks and top_banks.get("offline"):
        text += "🏦 *ТОП-5 БАНКОВ (ОТДЕЛЕНИЯ)*\n"
        text += "─" * 30 + "\n\n"
        
        for i, bank in enumerate(top_banks.get("offline", [])[:5], 1):
            text += f"*{i}. {bank.get('bank', '—')}*\n"
            text += f"📍 {bank.get('address', '—')}\n"
            text += f"💵 USD: {bank.get('usd_buy', 0):.4f} / {bank.get('usd_sell', 0):.4f}  |  Спред: {bank.get('usd_sell', 0) - bank.get('usd_buy', 0):.4f}\n"
            text += f"💶 EUR: {bank.get('eur_buy', 0):.4f} / {bank.get('eur_sell', 0):.4f}  |  Спред: {bank.get('eur_sell', 0) - bank.get('eur_buy', 0):.4f}\n\n"
    
    if top_banks and top_banks.get("best_buy") and top_banks.get("best_sell"):
        text += "⭐ *ЛУЧШИЕ ПРЕДЛОЖЕНИЯ*\n"
        text += "─" * 30 + "\n"
        
        best_buy = top_banks.get("best_buy")
        buy_key = f"{currency.lower()}_buy"
        text += f"🟢 Покупка: {best_buy.get('bank', '—')} ({best_buy.get('type', '—')}) — {best_buy.get(buy_key, '—')}\n"
        
        best_sell = top_banks.get("best_sell")
        sell_key = f"{currency.lower()}_sell"
        text += f"🔴 Продажа: {best_sell.get('bank', '—')} ({best_sell.get('type', '—')}) — {best_sell.get(sell_key, '—')}\n\n"
    
    text += "═" * 35 + "\n"
    text += "📎 *ИСТОЧНИКИ ДАННЫХ*\n"
    text += "═" * 35 + "\n"
    for source in sources[:4]:
        text += f"• {source.split('—')[0].strip()}\n"
    text += "\n"
    
    text += legal_disclaimer()
    return text

# ============================================================
# ФОНОВОЕ ОБНОВЛЕНИЕ ДАННЫХ
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
            logging.info("✅ Данные обновлены для всех городов")
        except Exception as e:
            logging.error(f"❌ Ошибка обновления: {e}")
        await asyncio.sleep(3600)

async def check_spam(user_id):
    now = datetime.now()
    last = USER_LAST_MESSAGE.get(user_id)
    if last and (now - last).seconds < 3:
        return True
    USER_LAST_MESSAGE[user_id] = now
    return False

def check_subscription(func):
    async def wrapper(callback_or_message, *args, **kwargs):
        user_id = callback_or_message.from_user.id
        status = get_subscription_status(user_id)
        if status == "expired":
            await callback_or_message.answer(
                "⏳ Ваша подписка истекла.\n"
                "Оплатите доступ через ЕРИП.\n"
                "После оплаты нажмите /confirm_payment",
                reply_markup=main_menu(user_id)
            )
            return
        return await func(callback_or_message, *args, **kwargs)
    return wrapper

# ============================================================
# КОМАНДА /START — НОВАЯ ВЕРСИЯ С ВЫБОРОМ ЯЗЫКА
# ============================================================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or "пользователь"
    
    user = db.get_user(user_id)
    
    # Если пользователь уже принял соглашение — сразу главное меню
    if user and db.has_accepted_agreement(user_id):
        lang = get_user_lang(user_id)
        await message.answer(
            f"🤖 *С возвращением, {first_name}!*\n\n"
            f"Выберите действие:",
            reply_markup=main_menu(user_id),
            parse_mode="Markdown"
        )
        return
    
    # Проверяем реферала
    args = message.text.split()
    referral_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referral_id = int(args[1].split("_")[1])
        except:
            pass
    
    # Регистрируем нового пользователя
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
            except:
                pass
    
    # Показываем яркое приветствие с выбором языка
    await message.answer(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=welcome_keyboard()
    )

# ============================================================
# ОБРАБОТЧИК ВЫБОРА ЯЗЫКА ИЗ ПРИВЕТСТВИЯ
# ============================================================

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
        "🌍 *Выберите язык / Choose language:*\n\n"
        "После выбора языка вы сможете ознакомиться с условиями использования.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ============================================================
# УСТАНОВКА ЯЗЫКА И ПОКАЗ СОГЛАШЕНИЯ
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    
    if lang_code in LANGUAGES:
        db.set_language(user_id, lang_code)
        await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang_code]['name']}")
        
        # Показываем соглашение на выбранном языке
        lang = get_user_lang(user_id)
        
        # Простой перевод соглашения (для демонстрации)
        if lang_code == "be":
            agreement_text = AGREEMENT_TEXT.replace("Сервис", "Сэрвіс").replace("Пользователь", "Карыстальнік")
        elif lang_code == "en":
            agreement_text = "📋 *TERMS OF USE*\n\nPlease read the terms carefully.\n\nBy clicking 'I accept', you agree to all terms."
        elif lang_code == "pl":
            agreement_text = "📋 *REGULAMIN*\n\nProsimy o zapoznanie się z warunkami.\n\nKlikając 'Akceptuję', zgadzasz się na wszystkie warunki."
        elif lang_code == "ua":
            agreement_text = "📋 *УГОДА КОРИСТУВАЧА*\n\nБудь ласка, ознайомтеся з умовами.\n\nНатискаючи 'Я приймаю', ви погоджуєтеся з усіма умовами."
        elif lang_code == "lt":
            agreement_text = "📋 *NAUDOJIMO SĄLYGOS*\n\nPrašome susipažinti su sąlygomis.\n\nSpustelėdami 'Sutinku', sutinkate su visomis sąlygomis."
        else:
            agreement_text = AGREEMENT_TEXT
        
        await callback.message.edit_text(
            agreement_text,
            parse_mode="Markdown",
            reply_markup=agreement_keyboard()
        )
    else:
        await callback.answer("❌ Неверный язык")

# ============================================================
# ПРИНЯТИЕ СОГЛАШЕНИЯ
# ============================================================

@dp.callback_query(lambda c: c.data == "accept_agreement")
async def accept_agreement(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if db.has_accepted_agreement(user_id):
        await callback.answer("✅ Вы уже приняли соглашение.")
        lang = get_user_lang(user_id)
        await callback.message.edit_text(
            f"🤖 *Добро пожаловать в BYN Super Investor Bot!*\n\n"
            f"Теперь вам доступны все функции:\n"
            f"• 📊 Курсы валют\n"
            f"• 🏦 ТОП-10 банков в вашем городе\n"
            f"• 🤖 AI-прогнозы USD и EUR\n"
            f"• 📈 Анализ рынка\n"
            f"• 👥 Реферальная программа\n"
            f"• 💳 Оформление подписки\n\n"
            f"Выберите действие:",
            reply_markup=main_menu(user_id),
            parse_mode="Markdown"
        )
        return
    
    db.accept_agreement(user_id)
    await callback.answer("✅ Соглашение принято!")
    
    lang = get_user_lang(user_id)
    await callback.message.edit_text(
        f"🤖 *Добро пожаловать в BYN Super Investor Bot!*\n\n"
        f"Теперь вам доступны все функции:\n"
        f"• 📊 Курсы валют\n"
        f"• 🏦 ТОП-10 банков в вашем городе\n"
        f"• 🤖 AI-прогнозы USD и EUR\n"
        f"• 📈 Анализ рынка\n"
        f"• 👥 Реферальная программа\n"
        f"• 💳 Оформление подписки\n\n"
        f"Выберите действие:",
        reply_markup=main_menu(user_id),
        parse_mode="Markdown"
    )

# ============================================================
# ОТКАЗ ОТ СОГЛАШЕНИЯ
# ============================================================

@dp.callback_query(lambda c: c.data == "decline_agreement")
async def decline_agreement(callback: types.CallbackQuery):
    await callback.answer("❌ Вы отказались от соглашения.")
    await callback.message.edit_text(
        "❌ Вы отказались от условий использования.\n\n"
        "Если передумаете, просто напишите /start снова.\n"
        "Мы будем рады видеть вас снова! 😊",
        parse_mode="Markdown"
    )

# ============================================================
# ОСТАЛЬНЫЕ КОМАНДЫ (без изменений)
# ============================================================

@dp.message(Command("agreement"))
async def show_agreement_command(message: types.Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if user and db.has_accepted_agreement(user_id):
        await message.answer(
            "✅ Вы уже приняли соглашение.\n\n"
            "Вы можете перечитать его ниже:",
            parse_mode="Markdown"
        )
    
    await message.answer(
        AGREEMENT_TEXT,
        parse_mode="Markdown",
        reply_markup=agreement_keyboard()
    )

@dp.message(Command("city"))
async def select_city_command(message: types.Message):
    user_id = message.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    for city in CITIES:
        buttons.append(InlineKeyboardButton(text=city, callback_data=f"city_{city}"))
    
    for i in range(0, len(buttons), 3):
        keyboard.inline_keyboard.append(buttons[i:i+3])
    
    await message.answer(
        "🌍 *Выберите город для отображения банков:*\n\n"
        "Бот покажет топ-10 банков в выбранном городе.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "city")
async def select_city_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text(
            "⚠️ Сначала примите соглашение: /agreement",
            reply_markup=main_menu(user_id)
        )
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    for city in CITIES:
        buttons.append(InlineKeyboardButton(text=city, callback_data=f"city_{city}"))
    
    for i in range(0, len(buttons), 3):
        keyboard.inline_keyboard.append(buttons[i:i+3])
    
    await callback.message.edit_text(
        "🌍 *Выберите город для отображения банков:*\n\n"
        "Бот покажет топ-10 банков в выбранном городе.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("city_"))
async def set_city(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    city = callback.data.replace("city_", "")
    
    if city in CITIES:
        db.set_city(user_id, city)
        await callback.answer(f"✅ Город изменён на {city}")
        await callback.message.edit_text(
            f"✅ Город для отображения банков: *{city}*\n\n"
            f"Теперь команда /banks покажет банки в {city}.",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
    else:
        await callback.answer("❌ Город не найден")

@dp.callback_query(lambda c: c.data == "banks")
async def get_banks_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text(
            "⚠️ Сначала примите соглашение: /agreement",
            reply_markup=main_menu(user_id)
        )
        return
    
    city = get_user_city(user_id)
    
    try:
        banks_data = CACHE_DATA.get("banks", {})
        banks = banks_data.get(city, {})
        offline = banks.get("offline", []) if banks else []
        online = banks.get("online", []) if banks else []
        
        if not offline and not online:
            await parser.get_bank_rates_for_city(city)
            banks = parser.banks_data.get(city, {})
            offline = banks.get("offline", []) if banks else []
            online = banks.get("online", []) if banks else []
        
        if not offline and not online:
            await callback.message.edit_text(
                f"⏳ Данные для {city} загружаются...\nПопробуйте через минуту.",
                reply_markup=main_menu(user_id)
            )
            return
        
        text = f"🏦 *ТОП-10 банков {city}*\n"
        text += "═" * 30 + "\n\n"
        
        if online:
            text += "📱 *ОНЛАЙН (лучшие курсы)*\n"
            text += "─" * 25 + "\n"
            for i, bank in enumerate(online[:5], 1):
                text += f"*{i}. {bank['bank']}*\n"
                text += f"💵 USD: {bank['usd_buy']:.4f} / {bank['usd_sell']:.4f}\n"
                text += f"💶 EUR: {bank['eur_buy']:.4f} / {bank['eur_sell']:.4f}\n\n"
        
        if offline:
            text += "🏦 *ОТДЕЛЕНИЯ*\n"
            text += "─" * 25 + "\n"
            for i, bank in enumerate(offline[:5], 1):
                text += f"*{i}. {bank['bank']}*\n"
                text += f"📍 {bank.get('address', '—')}\n"
                text += f"💵 USD: {bank['usd_buy']:.4f} / {bank['usd_sell']:.4f}\n"
                text += f"💶 EUR: {bank['eur_buy']:.4f} / {bank['eur_sell']:.4f}\n\n"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    except Exception as e:
        await callback.message.edit_text(
            f"⚠️ Ошибка получения данных для {city}",
            reply_markup=main_menu(user_id)
        )

@dp.callback_query(lambda c: c.data == "rates")
async def get_rates(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    nbrb_data = CACHE_DATA.get('nbrb', {})
    usd_rate = nbrb_data.get('usd', {}).get('nbrb', '—')
    eur_rate = nbrb_data.get('eur', {}).get('nbrb', '—')
    text = f"📊 *Курсы НБРБ*\n🇺🇸 USD/BYN: {usd_rate}\n🇪🇺 EUR/BYN: {eur_rate}\n"
    if LAST_UPDATE:
        text += f"\n🕒 Обновлено: {LAST_UPDATE.strftime('%d.%m.%Y %H:%M')}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "forecast_usd")
@check_subscription
async def forecast_usd(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    current_rate = CACHE_DATA.get("nbrb", {}).get("usd", {}).get("nbrb", 3.0)
    historical = [2.95, 2.97, 2.98, 2.99, 3.0, 2.99, 2.98, 2.97, 2.96, 2.95]
    
    city = get_user_city(user_id)
    banks_data = CACHE_DATA.get("banks", {}).get(city, {})
    all_banks = banks_data.get("offline", []) + banks_data.get("online", [])
    
    forecast = await ai.generate_forecast("USD", current_rate, historical, all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "forecast_eur")
@check_subscription
async def forecast_eur(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    current_rate = CACHE_DATA.get("nbrb", {}).get("eur", {}).get("nbrb", 3.45)
    historical = [3.40, 3.42, 3.43, 3.44, 3.45, 3.44, 3.43, 3.42, 3.41, 3.40]
    
    city = get_user_city(user_id)
    banks_data = CACHE_DATA.get("banks", {}).get(city, {})
    all_banks = banks_data.get("offline", []) + banks_data.get("online", [])
    
    forecast = await ai.generate_forecast("EUR", current_rate, historical, all_banks)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "analysis")
@check_subscription
async def analysis(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    forex = CACHE_DATA.get("forex", {})
    usd_rate = CACHE_DATA.get("nbrb", {}).get("usd", {}).get("nbrb", '—')
    eur_rate = CACHE_DATA.get("nbrb", {}).get("eur", {}).get("nbrb", '—')
    text = (f"📈 *Анализ рынка*\n\n🇺🇸 USD/BYN: {usd_rate}\n🇪🇺 EUR/BYN: {eur_rate}\n🇷🇺 USD/RUB: {forex.get('usd_rub', '—')}\n🌍 DXY: {forex.get('dxy', '—')}\n🛢️ Brent: {forex.get('brent', '—')}\n🇪🇺 EUR/USD: {forex.get('eur_usd', '—')}\n\n💡 *Влияние на курс BYN:*\n• Российский рубль — ключевой фактор\n• Цена нефти влияет на RUB\n• 20-е числа — налоговый период\n• Корреляция с USD/RUB: 0.89")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "subscribe")
async def subscribe_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    payment = generate_erip_payment(user_id)
    text = f"💳 *Оформление подписки*\n\n💳 Номер карты: {payment['receiver_card']}\n🏦 Банк: {payment['receiver_bank']}\n💰 Сумма: {payment['amount']}\n📋 Назначение: {payment['purpose']}\n\n🔗 Ссылка: {payment['erip_link']}\n\nПосле оплаты нажмите /confirm_payment"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("subscribe"))
async def subscribe_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Вы не зарегистрированы. Напишите /start")
        return
    payment = generate_erip_payment(user_id)
    text = f"💳 *Оформление подписки*\n\n💳 Номер карты: {payment['receiver_card']}\n🏦 Банк: {payment['receiver_bank']}\n💰 Сумма: {payment['amount']}\n📋 Назначение: {payment['purpose']}\n\n🔗 Ссылка: {payment['erip_link']}\n\nПосле оплаты нажмите /confirm_payment"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код операции.\nПример: `/confirm ERIP000123456`", parse_mode="Markdown")
        return
    payment_code = args[1].strip()
    if db.add_pending_payment(user_id, payment_code, "29.90 BYN"):
        await bot.send_message(ADMIN_ID, f"💳 *Новый платёж!*\n\n👤 @{message.from_user.username or 'без username'}\n📱 ID: {user_id}\n🔑 Код: `{payment_code}`\n💰 29.90 BYN\n\n✅ `/approve {payment_code}`")
        await message.answer(f"✅ Код `{payment_code}` сохранён! Ожидайте подтверждения.", parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await message.answer("⚠️ Ошибка сохранения платежа.", reply_markup=main_menu(user_id))

@dp.message(Command("approve"))
async def approve_payment(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код операции.\nПример: `/approve ERIP000123456`")
        return
    payment_code = args[1].strip()
    user_id = db.approve_payment(payment_code)
    if not user_id:
        await message.answer(f"❌ Платёж с кодом `{payment_code}` не найден.", parse_mode="Markdown")
        return
    subscription_end = get_subscription_end_date()
    db.update_user(user_id, {"status": "active", "subscription_end": subscription_end})
    await bot.send_message(user_id, f"✅ *Платёж подтверждён!* Подписка активна до {subscription_end}.", parse_mode="Markdown")
    await message.answer(f"✅ Платёж подтверждён! Пользователь {user_id} активирован до {subscription_end}")

@dp.message(Command("profile"))
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    user = db.get_user(user_id)
    if not user:
        await message.answer("Вы не зарегистрированы. Напишите /start")
        return
    status = get_subscription_status(user_id)
    city = get_user_city(user_id)
    text = f"📊 *Ваш профиль*\n\n👤 Имя: {user.get('first_name')}\n🌍 Город: {city}\n📌 Статус: {status}\n"
    if status == "trial":
        text += f"⏳ Пробный период до: {user.get('trial_end')}"
    elif status == "active":
        text += f"✅ Подписка до: {user.get('subscription_end')}"
    else:
        text += "❌ Подписка истекла"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.message.edit_text("Вы не зарегистрированы. Напишите /start", reply_markup=main_menu(user_id))
        return
    
    status = get_subscription_status(user_id)
    city = get_user_city(user_id)
    text = f"📊 *Ваш профиль*\n\n👤 Имя: {user.get('first_name')}\n🌍 Город: {city}\n📌 Статус: {status}\n"
    if status == "trial":
        text += f"⏳ Пробный период до: {user.get('trial_end')}"
    elif status == "active":
        text += f"✅ Подписка до: {user.get('subscription_end')}"
    else:
        text += "❌ Подписка истекла"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("referral"))
async def referral_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    user = db.get_user(user_id)
    if not user:
        await message.answer("Вы не зарегистрированы. Напишите /start")
        return
    referral_link = f"https://t.me/byn_investor_bot?start=ref_{user_id}"
    stats = db.get_referral_stats(user_id)
    text = f"👥 *Реферальная программа*\n\n🔗 *Ваша ссылка:*\n`{referral_link}`\n\n📊 *Статистика:*\n• Приглашено: {stats['total_referrals'] if stats else 0}\n• Активных: {stats['active_referrals'] if stats else 0}\n• Бонусных дней: {stats['bonus_days'] if stats else 0}"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "referral")
async def referral_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.message.edit_text("Вы не зарегистрированы. Напишите /start", reply_markup=main_menu(user_id))
        return
    
    referral_link = f"https://t.me/byn_investor_bot?start=ref_{user_id}"
    stats = db.get_referral_stats(user_id)
    text = f"👥 *Реферальная программа*\n\n🔗 *Ваша ссылка:*\n`{referral_link}`\n\n📊 *Статистика:*\n• Приглашено: {stats['total_referrals'] if stats else 0}\n• Активных: {stats['active_referrals'] if stats else 0}\n• Бонусных дней: {stats['bonus_days'] if stats else 0}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))

@dp.message(Command("support"))
async def support_command(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await message.answer(
        "🤖 *Консультант*\n\nНапишите ваш вопрос. Если я не смогу ответить — переключу на эксперта.",
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@dp.callback_query(lambda c: c.data == "support")
async def support_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    
    await callback.message.edit_text(
        "🤖 *Консультант*\n\nНапишите ваш вопрос. Если я не смогу ответить — переключу на эксперта.",
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@dp.message(Command("connect"))
async def connect_to_expert(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await bot.send_message(ADMIN_ID, f"🆘 *Запрос на консультацию!*\n\n👤 @{message.from_user.username or 'без username'}\n📱 ID: {user_id}\n\nДля ответа: `/reply {user_id} Ваш ответ`")
    await message.answer("🆘 Запрос передан эксперту. Ожидайте ответа.", reply_markup=main_menu(user_id))

@dp.message(Command("reply"))
async def reply_to_user(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Использование: `/reply <user_id> <текст>`")
        return
    try:
        target_user_id = int(args[1])
        reply_text = args[2]
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    await bot.send_message(target_user_id, f"📩 *Ответ эксперта:*\n\n{reply_text}", parse_mode="Markdown")
    await message.answer(f"✅ Ответ отправлен пользователю {target_user_id}")

@dp.message(Command("lang"))
async def change_language_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇧🇾 Беларуская", callback_data="lang_be")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇵🇱 Polski", callback_data="lang_pl")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton(text="🇱🇹 Lietuvių", callback_data="lang_lt")]
    ])
    await message.answer(
        "🌍 *Выберите язык / Choose language:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "change_lang")
async def show_languages_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
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
async def set_language_from_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    if lang_code in LANGUAGES:
        db.set_language(user_id, lang_code)
        await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang_code]['name']}")
        lang = get_user_lang(user_id)
        await callback.message.edit_text(
            lang["start"],
            reply_markup=main_menu(user_id),
            parse_mode="Markdown"
        )
    else:
        await callback.answer("❌ Неверный язык")

@dp.callback_query(lambda c: c.data == "agreement")
async def agreement_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if user and db.has_accepted_agreement(user_id):
        await callback.message.edit_text(
            "✅ Вы уже приняли соглашение.\n\n"
            "Вы можете перечитать его ниже:",
            parse_mode="Markdown"
        )
    
    await callback.message.edit_text(
        AGREEMENT_TEXT,
        parse_mode="Markdown",
        reply_markup=agreement_keyboard()
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    finance = get_financial_stats()
    forecast = get_forecast_stats()
    text = (f"🔐 *АДМИН-ПАНЕЛЬ*\n\n📊 *ФИНАНСЫ*\n💰 Общий доход: {finance['total_revenue']} BYN\n📈 За месяц: {finance['monthly_revenue']} BYN\n📅 За год: {finance['yearly_revenue']} BYN\n👥 Активных: {finance['active_subscriptions']}\n⏳ Пробный: {finance['trial_users']}\n❌ Просрочено: {finance['expired_users']}\n\n📈 *ПРОГНОЗЫ*\n🎯 Точность: {forecast['accuracy']}%\n🇺🇸 USD: {forecast['usd']['accuracy']}% ({forecast['usd']['total']})\n🇪🇺 EUR: {forecast['eur']['accuracy']}% ({forecast['eur']['total']})")
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("admin users"))
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    users = db.data["users"]
    text = "👥 *СПИСОК ПОЛЬЗОВАТЕЛЕЙ*\n\n"
    for user in users[:20]:
        status = user.get("status", "unknown")
        status_emoji = "✅" if status == "active" else "⏳" if status == "trial" else "❌"
        text += f"{status_emoji} @{user.get('username', 'без username')} | ID: {user.get('id')}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("admin user"))
async def admin_user_detail(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: `/admin user <id>`")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    user = db.get_user(target_id)
    if not user:
        await message.answer("Пользователь не найден.")
        return
    total_paid = sum([float(p.get("amount", 0)) for p in user.get("payment_history", [])])
    total_forecasts = len(user.get("forecast_history", []))
    correct_forecasts = len([f for f in user.get("forecast_history", []) if f.get("actual_result") == "WIN"])
    accuracy = round(correct_forecasts / total_forecasts * 100, 1) if total_forecasts > 0 else 0
    text = (f"👤 *ДЕТАЛИ ПОЛЬЗОВАТЕЛЯ*\n\n📱 ID: {user.get('id')}\n👤 Имя: {user.get('first_name')}\n📌 Статус: {user.get('status')}\n💳 Подписка до: {user.get('subscription_end')}\n💰 Всего оплачено: {total_paid} BYN\n📈 Прогнозов: {total_forecasts} | Точность: {accuracy}%\n\n📋 *ИСТОРИЯ ПЛАТЕЖЕЙ:*")
    for payment in user.get("payment_history", [])[-5:]:
        text += f"\n• {payment.get('date')}: {payment.get('amount')} BYN ({payment.get('status')})"
    await message.answer(text, parse_mode="Markdown")

@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    if await check_spam(user_id):
        return
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    from ai_support import AISupport
    ai_support = AISupport()
    response = await ai_support.get_response(message.text)
    if response.get("escalate"):
        await bot.send_message(
            ADMIN_ID,
            f"🆘 *Вопрос от @{message.from_user.username or 'без username'}*\n📝 {message.text}\n\nДля ответа: `/reply {user_id} Ваш ответ`",
            parse_mode="Markdown"
        )
        await message.answer("🆘 Вопрос передан эксперту. Ожидайте ответа.", reply_markup=main_menu(user_id))
    else:
        await message.answer(response["text"], parse_mode="Markdown", reply_markup=main_menu(user_id))

# ============================================================
# ЗАПУСК БОТА
# ============================================================

# Глобальный сет для хранения ссылок на фоновые задачи
background_tasks = set()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Бот запущен")
    
    # Создаём фоновую задачу и сохраняем ссылку на неё
    task = asyncio.create_task(update_data())
    background_tasks.add(task)
    # Удаляем из сета, когда задача завершится (если она не бесконечная)
    task.add_done_callback(background_tasks.discard)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
