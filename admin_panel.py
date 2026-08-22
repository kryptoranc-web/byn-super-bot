import os
import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from users_db import UserDB

db = UserDB()
admin_router = Router()

ADMIN_ID = int(os.environ.get("ADMIN_ID", 8064308550))

def is_admin(user_id: int) -> bool:
    """Строгая проверка прав администратора."""
    return user_id == ADMIN_ID

def check_user_access(user_id: int) -> bool:
    """
    Проверяет активность подписки. 
    Администратор имеет вечный бесплатный доступ.
    """
    if is_admin(user_id):
        return True

    user = db.get_user(user_id)
    if not user:
        return False
        
    status = user.get("status", "expired")
    days_left = user.get("days_left", 0)
    
    return status == "active" and days_left > 0

def get_admin_reply_keyboard() -> types.ReplyKeyboardMarkup:
    """Эргономичная клавиатура только для администратора."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏙 Выбрать город")
    builder.button(text="📊 Анализ рынка")
    builder.button(text="🤖 AI-Прогноз USD")
    builder.button(text="🤖 AI-Прогноз EUR")
    builder.button(text="👥 Управление клиентами")
    builder.button(text="💵 Финансы")
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_enhanced_financial_stats():
    """Безопасный расчет доходов и статистики пользователей."""
    total_revenue = 0.0
    monthly_revenue = 0.0
    semi_annual_revenue = 0.0
    yearly_revenue = 0.0
    
    active_subscriptions = 0
    expired_users = 0
    users_list = db.get_all_users()
    total_users = len(users_list)

    now = datetime.now()
    current_month = now.month
    current_year = now.year
    six_months_ago = now - timedelta(days=180)

    for user in users_list:
        for payment in user.get("payment_history", []):
            try:
                amount = float(payment.get("amount", 0))
                total_revenue += amount
                payment_date = datetime.fromisoformat(payment.get("date"))
                
                if payment_date.month == current_month and payment_date.year == current_year:
                    monthly_revenue += amount
                if payment_date >= six_months_ago:
                    semi_annual_revenue += amount
                if payment_date.year == current_year:
                    yearly_revenue += amount
            except Exception:
                continue

        if user.get("status") == "active" and user.get("days_left", 0) > 0:
            active_subscriptions += 1
        else:
            expired_users += 1

    return {
        "total_users": total_users,
        "total_revenue": round(total_revenue, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "semi_annual_revenue": round(semi_annual_revenue, 2),
        "yearly_revenue": round(yearly_revenue, 2),
        "active_subscriptions": active_subscriptions,
        "expired_users": expired_users
    }

# ================= CLIENT MANAGEMENT =================
@admin_router.message(F.text == "👥 Управление клиентами")
async def admin_manage_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return

    users = db.get_all_users()
    if not users:
        await message.answer("📭 База клиентов пуста.")
        return

    text = "👥 **Панель управления клиентами:**\nВыберите клиента для изменения подписки:\n\n"
    builder = InlineKeyboardBuilder()

    for user in users[:15]:
        uid = user.get("id")
        name = user.get("name") or user.get("first_name", "Клиент")
        days = user.get("days_left", 0)
        status = user.get("status", "expired")
        
        icon = "🟢" if status == "active" and days > 0 else "🔴"
        builder.button(text=f"{icon} {name} ({days} дн.)", callback_data=f"edit_user_{uid}")

    builder.adjust(1)
    builder.button(text="🔙 Назад в меню", callback_data="admin_back_main")
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@admin_router.callback_query(F.data.in_({"admin_users_list_back", "admin_users_list"}))
async def show_users_list_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return

    users = db.get_all_users()
    if not users:
        await callback.message.edit_text("📭 База клиентов пуста.")
        await callback.answer()
        return

    text = "👥 **Панель управления клиентами:**\nВыберите клиента для изменения подписки:\n\n"
    builder = InlineKeyboardBuilder()

    for user in users[:15]:
        uid = user.get("id")
        name = user.get("name") or user.get("first_name", "Клиент")
        days = user.get("days_left", 0)
        status = user.get("status", "expired")
        
        icon = "🟢" if status == "active" and days > 0 else "🔴"
        builder.button(text=f"{icon} {name} ({days} дн.)", callback_data=f"edit_user_{uid}")

    builder.adjust(1)
    builder.button(text="🔙 Назад в меню", callback_data="admin_back_main")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@admin_router.callback_query(F.data.startswith("edit_user_"))
async def edit_user_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        target_uid = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка обработки данных.", show_alert=True)
        return

    target_user = db.get_user(target_uid)
    if not target_user:
        await callback.answer("❌ Клиент не найден в базе!", show_alert=True)
        return

    text = (
        f"⚙️ **Управление клиентом:**\n"
        f"• Имя: {target_user.get('name') or target_user.get('first_name', 'Не указано')}\n"
        f"• ID: `{target_uid}`\n"
        f"• Статус: *{target_user.get('status', 'expired')}*\n"
        f"• Осталось дней: **{target_user.get('days_left', 0)}**"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить 7 дней", callback_data=f"set_days_{target_uid}_7")
    builder.button(text="➕ Добавить 30 дней", callback_data=f"set_days_{target_uid}_30")
    builder.button(text="🚫 Заблокировать (0 дней)", callback_data=f"set_days_{target_uid}_0")
    builder.button(text="🔙 К списку клиентов", callback_data="admin_users_list_back")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@admin_router.callback_query(F.data.startswith("set_days_"))
async def set_user_days(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        parts = callback.data.split("_")
        target_uid = int(parts[2])
        days_to_set = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка формата данных.", show_alert=True)
        return

    target_user = db.get_user(target_uid)
    if target_user:
        new_sub_end = (datetime.now() + timedelta(days=days_to_set)).isoformat() if days_to_set > 0 else datetime.now().isoformat()
        db.update_user(target_uid, {"subscription_end": new_sub_end})
        await callback.answer(f"✅ Успешно! Установлено дней: {days_to_set}", show_alert=True)
        await edit_user_panel(callback)
    else:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)

@admin_router.callback_query(F.data == "admin_back_main")
async def back_to_admin_main(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.delete()
    await callback.answer()

@admin_router.message(F.text == "💵 Финансы")
async def admin_finances(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    stats = get_enhanced_financial_stats()
    text = (
        f"💵 **Финансовая статистика:**\n\n"
        f"• Общий доход: **{stats['total_revenue']} BYN**\n"
        f"• За текущий месяц: **{stats['monthly_revenue']} BYN**\n"
        f"• За полугодие (6 мес): **{stats['semi_annual_revenue']} BYN**\n"
        f"• За год: **{stats['yearly_revenue']} BYN**\n\n"
        f"👥 Всего клиентов: `{stats['total_users']}`\n"
        f"🟢 С активной подпиской: `{stats['active_subscriptions']}`"
    )
    await message.answer(text, parse_mode="Markdown")

# ================= PAYMENT NOTIFICATIONS =================
async def notify_admin_new_payment(bot: Bot, user_id: int, user_name: str, amount: float):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить (+30 дней)", callback_data=f"approve_pay_{user_id}_30")
    builder.button(text="❌ Отклонить", callback_data=f"reject_pay_{user_id}")
    builder.adjust(1)

    text = (
        f"🔔 **Новая заявка на оплату!**\n\n"
        f"• От клиента: {user_name} (`{user_id}`)\n"
        f"• Сумма: **{amount} BYN**\n\n"
        f"Проверьте поступление и выберите действие:"
    )
    try:
        await bot.send_message(ADMIN_ID, text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление админу: {e}")

@admin_router.callback_query(F.data.startswith("approve_pay_"))
async def approve_payment(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        parts = callback.data.split("_")
        target_uid = int(parts[2])
        days_granted = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка подтверждения оплаты.", show_alert=True)
        return

    target_user = db.get_user(target_uid)
    if target_user:
        current_end = datetime.fromisoformat(target_user["subscription_end"]) if target_user.get("subscription_end") and datetime.fromisoformat(target_user["subscription_end"]) > datetime.now() else datetime.now()
        new_end = (current_end + timedelta(days=days_granted)).isoformat()
        
        # Добавляем платеж в историю
        payments = target_user.get("payment_history", [])
        payments.append({"date": datetime.now().isoformat(), "amount": "29.90"})
        
        db.update_user(target_uid, {
            "subscription_end": new_end,
            "status": "active",
            "payment_history": payments
        })

    try:
        await callback.bot.send_message(
            target_uid, 
            f"🎉 **Ваша оплата подтверждена!**\nВам начислено дней подписки: +{days_granted}. Приятного пользования!"
        )
    except Exception:
        pass

    await callback.message.edit_text(f"✅ Оплата для пользователя `{target_uid}` успешно подтверждена (+{days_granted} дней).", parse_mode="Markdown")
    await callback.answer("Подтверждено!")

@admin_router.callback_query(F.data.startswith("reject_pay_"))
async def reject_payment(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        target_uid = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка.", show_alert=True)
        return

    try:
        await callback.bot.send_message(
            target_uid, 
            "❌ К сожалению, ваша заявка на оплату была отклонена администратором. Обратитесь в поддержку."
        )
    except Exception:
        pass

    await callback.message.edit_text(f"❌ Заявка пользователя `{target_uid}` отклонена.", parse_mode="Markdown")
    await callback.answer("Отклонено.")
