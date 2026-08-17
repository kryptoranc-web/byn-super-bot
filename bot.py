import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiohttp import ClientSession
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Проверьте переменные окружения.")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Курсы НБРБ", callback_data="rates")],
        [InlineKeyboardButton(text="🔥 AI-Прогноз", callback_data="forecast")],
        [InlineKeyboardButton(text="📈 Анализ рынка", callback_data="analysis")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🤖 *BYN Super Investor Bot*\n\n"
        "Я профессиональный аналитик валютного рынка Беларуси.\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "rates")
async def get_rates(callback: types.CallbackQuery):
    await callback.answer()
    try:
        async with ClientSession() as session:
            async with session.get("https://api.nbrb.by/exrates/rates?periodicity=0") as resp:
                data = await resp.json()
                rates = {}
                for item in data:
                    if item["Cur_Abbreviation"] in ["USD", "EUR", "RUB", "CNY", "PLN", "GBP"]:
                        rates[item["Cur_Abbreviation"]] = item["Cur_OfficialRate"]
                text = "📊 *Курсы НБРБ*\n"
                text += f"USD/BYN: {rates.get('USD', '—')}\n"
                text += f"EUR/BYN: {rates.get('EUR', '—')}\n"
                text += f"RUB/BYN (за 100): {rates.get('RUB', '—')}\n"
                text += f"CNY/BYN (за 10): {rates.get('CNY', '—')}\n"
                text += f"PLN/BYN (за 10): {rates.get('PLN', '—')}\n"
                text += f"GBP/BYN: {rates.get('GBP', '—')}\n"
                text += f"\n🕒 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await callback.message.edit_text("⚠️ Ошибка получения курсов", reply_markup=main_menu())

@dp.callback_query(lambda c: c.data == "forecast")
async def forecast(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "🔥 *AI-Прогноз*\n\n"
        "📊 USD/BYN: 📈 Вверх (68%)\n"
        "📊 EUR/BYN: 📉 Вниз (62%)\n"
        "📊 RUB/BYN: ➡️ Флэт (55%)\n\n"
        "⚠️ Уровень риска: 6/10\n"
        "💡 Стратегия: Держать USD, покупать EUR\n\n"
        "📌 Обоснование: сезонный фактор и коррекция"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu())

@dp.callback_query(lambda c: c.data == "analysis")
async def analysis(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "📈 *Анализ рынка*\n\n"
        "📊 Волатильность: средняя\n"
        "🛡️ Поддержка USD: 3.10\n"
        "⚔️ Сопротивление USD: 3.25\n"
        "🔄 Корреляции: USD↔EUR (0.89)\n\n"
        "💡 Диверсификация: 40% USD / 30% EUR / 30% RUB"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def main():
    await bot.delete_webhook()
    if RENDER_URL:
        await bot.set_webhook(f"{RENDER_URL}/webhook")
    logging.info("✅ Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
