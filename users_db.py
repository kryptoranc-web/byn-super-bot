import json
import os
from datetime import datetime

DB_FILE = "users.json"

class UserDB:
    def __init__(self):
        self.data = {"users": []}
        self.load()

    def load(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                self.data = json.load(f)

    def save(self):
        with open(DB_FILE, 'w') as f:
            json.dump(self.data, f, indent=4, default=str)

    def get_user(self, user_id):
        for user in self.data["users"]:
            if user["id"] == user_id:
                return user
        return None

    def add_user(self, user_data):
        if not self.get_user(user_data["id"]):
            self.data["users"].append(user_data)
            self.save()
            return True
        return False

    def update_user(self, user_id, update_data):
        user = self.get_user(user_id)
        if user:
            user.update(update_data)
            self.save()
            return True
        return False

    def get_language(self, user_id):
        user = self.get_user(user_id)
        return user.get("language", "ru") if user else "ru"

    def set_language(self, user_id, lang):
        user = self.get_user(user_id)
        if user:
            user["language"] = lang
            self.save()
            return True
        return False

    def get_city(self, user_id):
        user = self.get_user(user_id)
        return user.get("city", "Минск") if user else "Минск"

    def set_city(self, user_id, city):
        user = self.get_user(user_id)
        if user:
            user["city"] = city
            self.save()
            return True
        return False

    def has_accepted_agreement(self, user_id):
        user = self.get_user(user_id)
        return user.get("agreement_accepted", False) if user else False

    def accept_agreement(self, user_id):
        user = self.get_user(user_id)
        if user:
            user["agreement_accepted"] = True
            user["agreement_date"] = datetime.now().isoformat()
            self.save()
            return True
        return False

    def add_referral(self, referrer_id, referred_id):
        referrer = self.get_user(referrer_id)
        if referrer:
            if "referrals" not in referrer:
                referrer["referrals"] = []
            if referred_id not in referrer["referrals"]:
                referrer["referrals"].append(referred_id)
                self.save()
                return True
        return False

    def get_referral_stats(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return None
        return {
            "total_referrals": len(user.get("referrals", [])),
            "active_referrals": len([r for r in user.get("referrals", []) if self.get_user(r) and self.get_user(r).get("status") == "active"]),
            "bonus_days": user.get("bonus_days", 0)
        }

    def add_pending_payment(self, user_id, payment_code, amount):
        user = self.get_user(user_id)
        if not user:
            return False
        if "pending_payments" not in user:
            user["pending_payments"] = []
        user["pending_payments"].append({
            "code": payment_code,
            "amount": amount,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        })
        self.save()
        return True

    def get_pending_payment(self, payment_code):
        for user in self.data["users"]:
            for payment in user.get("pending_payments", []):
                if payment["code"] == payment_code and payment["status"] == "pending":
                    return user["id"], payment
        return None, None

    def approve_payment(self, payment_code):
        user_id, payment = self.get_pending_payment(payment_code)
        if not user_id:
            return None
        payment["status"] = "approved"
        user = self.get_user(user_id)
        if "payment_history" not in user:
            user["payment_history"] = []
        user["payment_history"].append({
            "date": datetime.now().isoformat(),
            "amount": payment["amount"],
            "code": payment_code,
            "status": "approved"
        })
        self.save()
        return user_id
