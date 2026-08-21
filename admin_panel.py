from datetime import datetime
from users_db import UserDB

db = UserDB()
ADMIN_ID = 123456789  # ЗАМЕНИТЕ НА ВАШ ID

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_financial_stats():
    total_revenue = 0
    monthly_revenue = 0
    yearly_revenue = 0
    active_subscriptions = 0
    trial_users = 0
    expired_users = 0

    current_month = datetime.now().month
    current_year = datetime.now().year

    for user in db.data["users"]:
        for payment in user.get("payment_history", []):
            try:
                amount = float(payment.get("amount", 0))
                total_revenue += amount
                payment_date = datetime.fromisoformat(payment.get("date"))
                if payment_date.month == current_month and payment_date.year == current_year:
                    monthly_revenue += amount
                if payment_date.year == current_year:
                    yearly_revenue += amount
            except:
                continue

        status = user.get("status", "unknown")
        if status == "active":
            active_subscriptions += 1
        elif status == "trial":
            trial_users += 1
        elif status == "expired":
            expired_users += 1

    return {
        "total_revenue": round(total_revenue, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "yearly_revenue": round(yearly_revenue, 2),
        "active_subscriptions": active_subscriptions,
        "trial_users": trial_users,
        "expired_users": expired_users
    }

def get_forecast_stats():
    total_forecasts = 0
    correct_forecasts = 0
    usd_forecasts = {"total": 0, "correct": 0}
    eur_forecasts = {"total": 0, "correct": 0}

    for user in db.data["users"]:
        for forecast in user.get("forecast_history", []):
            total_forecasts += 1
            if forecast.get("actual_result") == "WIN":
                correct_forecasts += 1
            if forecast.get("currency") == "USD":
                usd_forecasts["total"] += 1
                if forecast.get("actual_result") == "WIN":
                    usd_forecasts["correct"] += 1
            elif forecast.get("currency") == "EUR":
                eur_forecasts["total"] += 1
                if forecast.get("actual_result") == "WIN":
                    eur_forecasts["correct"] += 1

    accuracy = (correct_forecasts / total_forecasts * 100) if total_forecasts > 0 else 0
    usd_accuracy = (usd_forecasts["correct"] / usd_forecasts["total"] * 100) if usd_forecasts["total"] > 0 else 0
    eur_accuracy = (eur_forecasts["correct"] / eur_forecasts["total"] * 100) if eur_forecasts["total"] > 0 else 0

    return {
        "total_forecasts": total_forecasts,
        "correct_forecasts": correct_forecasts,
        "accuracy": round(accuracy, 1),
        "usd": {"total": usd_forecasts["total"], "correct": usd_forecasts["correct"], "accuracy": round(usd_accuracy, 1)},
        "eur": {"total": eur_forecasts["total"], "correct": eur_forecasts["correct"], "accuracy": round(eur_accuracy, 1)}
  }
