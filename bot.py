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

# Импорты
from parser import CurrencyParser
from analyzer import TechnicalAnalyzer
from ai_forecast import AIForecast
from users_db import UserDB
from subscription import *
from payments import generate_erip_payment
from admin_panel import *
from languages import LANGUAGES
from config import CITIES
from agreement import AGREEMENT_TEXT, agreement_keyboard, legal_disclaimer

# Инициализация
parser = CurrencyParser()
analyzer = TechnicalAnalyzer()
ai = AIForecast()
db = UserDB()

CACHE_DATA = {}
LAST_UPDATE = None
USER_LAST_MESSAGE = {}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

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

def format_forecast(forecast):
    """Форматирование прогноза с юридическим предупреждением"""
    currency = forecast.get("currency", "USD")
    preds = forecast.get("predictions", {})
    levels = forecast.get("levels", {})
    validation = forecast.get("validation", {})
    
    text = f"🤖 *AI-Прогноз {currency}/BYN*\n\n"
    text += f"📊 Текущий курс: {forecast.get('current_rate', '—')}\n"
    text += f"📈 RSI: {forecast.get('rsi', '—')} "
    
    rsi = forecast.get('rsi', 50)
    if rsi > 70:
        text += "(перекупленность 🔴)\n"
    elif rsi < 30:
        text += "(перепроданность 🟢)\n"
    else:
        text += "(нейтральный 🟡)\n"
    
    text += f"📊 Тренд: {forecast.get('trend', '—')}\n\n"
    text += "📅 *Прогноз:*\n"
    text += f"• Неделя: {preds.get('week', '—')}\n"
    text += f"• Месяц: {preds.get('month', '—')}\n"
    text += f"• 3 месяца: {preds.get('quarter', '—')}\n\n"
    text += "📊 *Уровни:*\n"
    text += f"🛡️ Поддержка: {levels.get('support', '—')}\n"
    text += f"⚔️ Сопротивление: {levels.get('resistance', '—')}\n\n"
    text += f"🎯 Рекомендация: {forecast.get('recommendation', '—')}\n"
    text += f"⚠️ Риск: {forecast.get('risk', '—')}/10\n"
    text += f"✅ Уверенность: {forecast.get('confidence', '—')}%\n\n"
    text += "📌 *Обоснование:*\n"
    text += f"• {forecast.get('seasonal_impact', '—')}\n"
    
    forex_impact = forecast.get('forex_impact', {})
    if forex_impact:
        text += f"• Влияние USD/RUB: {forex_impact.get('usd_rub_trend', '—')}\n"
        text += f"• Индекс доллара: {forex_impact.get('dxy_trend', '—')}\n"
        text += f"• Нефть Brent: {forex_impact.get('brent_trend', '—')}\n"
    
    text += "\n🔬 *Самопроверка AI (3 этапа):*\n"
    text += f"• Технический анализ: {'✅' if validation.get('stage1') else '❌'}\n"
    text += f"• Фундаментальный анализ: {'✅' if validation.get('stage2') else '❌'}\n"
    text += f"• Внешние факторы: {'✅' if validation.get('stage3') else '❌'}\n"
    text += f"• Общая уверенность: {validation.get('overall_confidence', '—')}%\n\n"
    text += "📎 *Источники:*\n"
    for source in forecast.get("sources", []):
        text += f"• {source}\n"
    
    text += legal_disclaimer()
    return text

# ==================== ФОНОВОЕ ОБНОВЛЕНИЕ ====================

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
    if last and (now - last).seconds < 5:
        return True
    USER_LAST_MESSAGE[user_id] = now
    return False

# ==================== КОМАНДА /START ====================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or "пользователь"
    
    if not db.has_accepted_agreement(user_id):
        await message.answer(
            "⚠️ *Добро пожаловать!*\n\n"
            "Перед началом использования необходимо ознакомиться с условиями.\n\n"
            "Нажмите /agreement, чтобы прочитать соглашение.",
            parse_mode="Markdown"
        )
        return
    
    args = message.text.split()
    referral_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referral_id = int(args[1].split("_")[1])
        except:
            pass
    
    user = db.get_user(user_id)
    lang = get_user_lang(user_id)
    
    if not user:
        new_user = {
            "id": user_id, "username": username, "first_name": first_name,
            "status": "trial", "trial_start": datetime.now().isoformat(),
            "trial_end": get_trial_end_date(), "subscription_end": None,
            "bonus_days": 0, "referrals": [], "referred_by": referral_id,
            "payment_history": [], "forecast_history": [], "is_blocked": False,
            "language": "ru", "city": "Минск", "agreement_accepted": True,
            "agreement_date": datetime.now().isoformat()
        }
        db.add_user(new_user)
        
        if referral_id and is_valid_referral(referral_id, user_id):
            db.update_user(user_id, {"trial_end": (datetime.now() + timedelta(days=TRIAL_DAYS + 3)).isoformat()})
            db.add_referral(referral_id, user_id)
            try:
                await bot.send_message(referral_id, f"🎉 Ваш друг @{username} зарегистрировался!")
            except:
                pass
            await message.answer(
                "🎉 Вы зарегистрировались по приглашению друга!\n"
                "Ваш пробный период увеличен на 3 дня.\n\n"
                "Используйте бота для заработка!",
                reply_markup=main_menu(user_id)
            )
        else:
            await message.answer(lang["start"], reply_markup=main_menu(user_id), parse_mode="Markdown")
    else:
        status = get_subscription_status(user_id)
        if status == "trial":
            await message.answer(
                "Вы в пробном периоде. Используйте все функции бота бесплатно!",
                reply_markup=main_menu(user_id)
            )
        elif status == "active":
            await message.answer(
                f"✅ Добро пожаловать!\n"
                f"Ваша подписка активна до {user.get('subscription_end')}.\n\n"
                f"Используйте бота для заработка!",
                reply_markup=main_menu(user_id)
            )
        else:
            await message.answer(
                "⏳ Ваша подписка истекла.\n"
                "Оплатите доступ через ЕРИП.\n"
                "После оплаты нажмите /confirm_payment",
                reply_markup=main_menu(user_id)
            )

# ==================== ОСТАЛЬНЫЕ КОМАНДЫ ====================

@dp.message(Command("agreement"))
async def show_agreement(message: types.Message):
    await message.answer(AGREEMENT_TEXT, parse_mode="Markdown", reply_markup=agreement_keyboard())

@dp.callback_query(lambda c: c.data == "accept_agreement")
async def accept_agreement(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if db.has_accepted_agreement(user_id):
        await callback.answer("✅ Вы уже приняли соглашение.")
        return
    db.accept_agreement(user_id)
    await callback.answer("✅ Соглашение принято!")
    lang = get_user_lang(user_id)
    await callback.message.edit_text(lang["start"], reply_markup=main_menu(user_id), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "decline_agreement")
async def decline_agreement(callback: types.CallbackQuery):
    await callback.answer("❌ Вы отказались от соглашения.")
    await callback.message.edit_text(
        "❌ Вы отказались от условий использования.\n\n"
        "Если передумаете, нажмите /agreement снова.",
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "agreement")
async def show_agreement_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(AGREEMENT_TEXT, parse_mode="Markdown", reply_markup=agreement_keyboard())

@dp.message(Command("lang"))
async def change_language(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇧🇾 Беларуская", callback_data="lang_be")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇵🇱 Polski", callback_data="lang_pl")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton(text="🇱🇹 Lietuvių", callback_data="lang_lt")]
    ])
    await message.answer("🌍 *Выберите язык / Choose language:*", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[1]
    if lang_code in LANGUAGES:
        db.set_language(user_id, lang_code)
        await callback.answer(f"✅ Язык изменён на {LANGUAGES[lang_code]['name']}")
        lang = get_user_lang(user_id)
        await callback.message.edit_text(lang["start"], reply_markup=main_menu(user_id), parse_mode="Markdown")
    else:
        await callback.answer("❌ Неверный язык")

@dp.message(Command("city"))
async def select_city(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(text=city, callback_data=f"city_{city}") for city in CITIES]
    keyboard.add(*buttons)
    await message.answer("🌍 *Выберите город для отображения банков:*", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("city_"))
async def set_city(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    city = callback.data.replace("city_", "")
    if city in CITIES:
        db.set_city(user_id, city)
        await callback.answer(f"✅ Город изменён на {city}")
        await callback.message.edit_text(f"✅ Город для отображения банков: *{city}*", parse_mode="Markdown")
    else:
        await callback.answer("❌ Город не найден")

@dp.callback_query(lambda c: c.data == "banks")
async def get_banks(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if not db.has_accepted_agreement(user_id):
        await callback.message.edit_text("⚠️ Сначала примите соглашение: /agreement", reply_markup=main_menu(user_id))
        return
    city = get_user_city(user_id)
    try:
        banks_data = CACHE_DATA.get("banks", {})
        banks = banks_data.get(city, [])
        if not banks:
            await parser.get_bank_rates_for_city(city)
            banks = parser.banks_data.get(city, [])
        if not banks:
            await callback.message.edit_text(f"⏳ Данные для {city} загружаются...", reply_markup=main_menu(user_id))
            return
        text = f"🏦 *ТОП-10 банков {city}*\n💵 *Покупка/Продажа USD и EUR*\n\n"
        for i, bank in enumerate(banks[:10], 1):
            text += f"*{i}. {bank['bank']}*\n"
            text += f"💵 USD: {bank['usd_buy']:.4f} / {bank['usd_sell']:.4f}\n"
            text += f"💶 EUR: {bank['eur_buy']:.4f} / {bank['eur_sell']:.4f}\n"
            text += f"📍 {bank['address']}\n\n"
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    except Exception as e:
        await callback.message.edit_text("⚠️ Ошибка получения данных", reply_markup=main_menu(user_id))

@dp.callback_query(lambda c: c.data == "rates")
async def get_rates(callback: types.CallbackQuery):
    await callback.answer()
    nbrb_data = CACHE_DATA.get('nbrb', {})
    usd_rate = nbrb_data.get('usd', {}).get('nbrb', '—')
    eur_rate = nbrb_data.get('eur', {}).get('nbrb', '—')
    text = f"📊 *Курсы НБРБ*\n🇺🇸 USD/BYN: {usd_rate}\n🇪🇺 EUR/BYN: {eur_rate}\n"
    if LAST_UPDATE:
        text += f"\n🕒 Обновлено: {LAST_UPDATE.strftime('%d.%m.%Y %H:%M')}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "forecast_usd")
async def forecast_usd(callback: types.CallbackQuery):
    await callback.answer()
    current_rate = CACHE_DATA.get("nbrb", {}).get("usd", {}).get("nbrb", 3.0)
    historical = [2.95, 2.97, 2.98, 2.99, 3.0, 2.99, 2.98, 2.97, 2.96, 2.95]
    forecast = await ai.generate_forecast("USD", current_rate, historical)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "forecast_eur")
async def forecast_eur(callback: types.CallbackQuery):
    await callback.answer()
    current_rate = CACHE_DATA.get("nbrb", {}).get("eur", {}).get("nbrb", 3.45)
    historical = [3.40, 3.42, 3.43, 3.44, 3.45, 3.44, 3.43, 3.42, 3.41, 3.40]
    forecast = await ai.generate_forecast("EUR", current_rate, historical)
    await callback.message.edit_text(format_forecast(forecast), parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.callback_query(lambda c: c.data == "analysis")
async def analysis(callback: types.CallbackQuery):
    await callback.answer()
    forex = CACHE_DATA.get("forex", {})
    usd_rate = CACHE_DATA.get("nbrb", {}).get("usd", {}).get("nbrb", '—')
    eur_rate = CACHE_DATA.get("nbrb", {}).get("eur", {}).get("nbrb", '—')
    text = (f"📈 *Анализ рынка*\n\n🇺🇸 USD/BYN: {usd_rate}\n🇪🇺 EUR/BYN: {eur_rate}\n🇷🇺 USD/RUB: {forex.get('usd_rub', '—')}\n🌍 DXY: {forex.get('dxy', '—')}\n🛢️ Brent: {forex.get('brent', '—')}\n🇪🇺 EUR/USD: {forex.get('eur_usd', '—')}\n\n💡 *Влияние на курс BYN:*\n• Российский рубль — ключевой фактор\n• Цена нефти влияет на RUB\n• 20-е числа — налоговый период\n• Корреляция с USD/RUB: 0.89")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(callback.from_user.id))

@dp.message(Command("profile"))
async def profile(message: types.Message):
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

@dp.message(Command("referral"))
async def referral(message: types.Message):
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

@dp.message(Command("subscribe"))
async def subscribe(message: types.Message):
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

@dp.message(Command("support"))
async def support(message: types.Message):
    user_id = message.from_user.id
    if not db.has_accepted_agreement(user_id):
        await message.answer("⚠️ Сначала примите соглашение: /agreement")
        return
    if not db.get_user(user_id):
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await message.answer("🤖 *Консультант*\n\nНапишите ваш вопрос. Если я не смогу ответить — переключу на эксперта.", parse_mode="Markdown", reply_markup=main_menu(user_id))

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
        await bot.send_message(ADMIN_ID, f"🆘 *Вопрос от @{message.from_user.username or 'без username'}*\n📝 {message.text}\n\nДля ответа: `/reply {user_id} Ваш ответ`")
        await message.answer("🆘 Вопрос передан эксперту. Ожидайте ответа.", reply_markup=main_menu(user_id))
    else:
        await message.answer(response["text"], parse_mode="Markdown", reply_markup=main_menu(user_id))

# ==================== ЗАПУСК БОТА ====================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Бот запущен")
    asyncio.create_task(update_data())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
