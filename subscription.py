from datetime import datetime, timedelta
from users_db import UserDB

db = UserDB()

TRIAL_DAYS = 14
SUBSCRIPTION_PRICE = "29.90 BYN"
MAX_BONUS_DAYS_PER_MONTH = 30

def is_trial_active(user_id):
    user = db.get_user(user_id)
    if not user:
        return False
    trial_end = user.get("trial_end")
    if not trial_end:
        return False
    return datetime.now() <= datetime.fromisoformat(trial_end)

def is_subscription_active(user_id):
    user = db.get_user(user_id)
    if not user:
        return False
    subscription_end = user.get("subscription_end")
    if not subscription_end:
        return False
    return datetime.now() <= datetime.fromisoformat(subscription_end)

def get_subscription_status(user_id):
    if is_trial_active(user_id):
        return "trial"
    elif is_subscription_active(user_id):
        return "active"
    return "expired"

def get_trial_end_date():
    return (datetime.now() + timedelta(days=TRIAL_DAYS)).isoformat()

def get_subscription_end_date():
    return (datetime.now() + timedelta(days=30)).isoformat()

def add_referral_bonus(user_id, days):
    user = db.get_user(user_id)
    if not user:
        return False
    current = user.get("bonus_days", 0)
    new_bonus = min(current + days, MAX_BONUS_DAYS_PER_MONTH)
    db.update_user(user_id, {"bonus_days": new_bonus})
    return True

def get_referral_bonus_for_referred(duration):
    return {1: 7, 3: 30, 6: 60}.get(duration, 0)

def get_referral_bonus_for_referrer(duration):
    return {1: 5, 3: 15, 6: 30}.get(duration, 0)

def is_valid_referral(referrer_id, referred_id):
    if referrer_id == referred_id:
        return False
    referrer = db.get_user(referrer_id)
    if referrer and referred_id in referrer.get("referrals", []):
        return False
    return True

def check_and_notify_expired():
    return [user for user in db.data["users"] if get_subscription_status(user["id"]) == "expired"]
