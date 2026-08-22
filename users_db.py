import sqlite3
import json
from datetime import datetime

class UserDB:
    def __init__(self, db_file="users.db"):
        self.db_file = db_file
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    name TEXT,
                    status TEXT,
                    trial_start TEXT,
                    trial_end TEXT,
                    subscription_end TEXT,
                    bonus_days INTEGER,
                    referrals TEXT,
                    referred_by INTEGER,
                    payment_history TEXT,
                    forecast_history TEXT,
                    is_blocked BOOLEAN,
                    language TEXT,
                    city TEXT,
                    agreement_accepted BOOLEAN
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    code TEXT,
                    amount TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()

    def get_user(self, user_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            user = dict(row)
            user["user_id"] = user["id"]  # Дублируем для совместимости с админкой
            user["referrals"] = json.loads(user["referrals"] or "[]")
            user["payment_history"] = json.loads(user["payment_history"] or "[]")
            user["forecast_history"] = json.loads(user["forecast_history"] or "[]")
            user["is_blocked"] = bool(user["is_blocked"])
            user["agreement_accepted"] = bool(user["agreement_accepted"])
            
            # Динамический расчет оставшихся дней и статуса подписки
            now = datetime.now()
            sub_end = datetime.fromisoformat(user["subscription_end"]) if user.get("subscription_end") else None
            trial_end = datetime.fromisoformat(user["trial_end"]) if user.get("trial_end") else None
            
            days_left = 0
            status = "expired"
            
            if sub_end and sub_end > now:
                days_left = (sub_end - now).days
                status = "active"
            elif trial_end and trial_end > now:
                days_left = (trial_end - now).days
                status = "active"
            
            user["days_left"] = max(0, days_left)
            user["status"] = status
            return user

    def get_all_users(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users")
            user_ids = [row["id"] for row in cursor.fetchall()]
        return [self.get_user(uid) for uid in user_ids]

    def add_user(self, user_data):
        uid = user_data.get("id") or user_data.get("user_id")
        name = user_data.get("name") or user_data.get("first_name", "Клиент")
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO users 
                (id, username, first_name, name, status, trial_start, trial_end, subscription_end, 
                 bonus_days, referrals, referred_by, payment_history, forecast_history, 
                 is_blocked, language, city, agreement_accepted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid, user_data.get("username"), user_data.get("first_name"), name,
                user_data.get("status", "trial"), user_data.get("trial_start"),
                user_data.get("trial_end"), user_data.get("subscription_end"),
                user_data.get("bonus_days", 0), json.dumps(user_data.get("referrals", [])),
                user_data.get("referred_by"), json.dumps(user_data.get("payment_history", [])),
                json.dumps(user_data.get("forecast_history", [])), int(user_data.get("is_blocked", False)),
                user_data.get("language", "ru"), user_data.get("city", "Минск"),
                int(user_data.get("agreement_accepted", False))
            ))
            conn.commit()

    def update_user(self, user_id, update_data):
        user = self.get_user(user_id)
        if not user:
            return
        user.update(update_data)
        self.add_user(user)

    def has_accepted_agreement(self, user_id):
        user = self.get_user(user_id)
        return user.get("agreement_accepted", False) if user else False

    def accept_agreement(self, user_id):
        self.update_user(user_id, {"agreement_accepted": True})

    def get_language(self, user_id):
        user = self.get_user(user_id)
        return user.get("language", "ru") if user else "ru"

    def get_city(self, user_id):
        user = self.get_user(user_id)
        return user.get("city", "Минск") if user else "Минск"

    def set_city(self, user_id, city):
        self.update_user(user_id, {"city": city})

    def add_referral(self, referrer_id, referee_id):
        referrer = self.get_user(referrer_id)
        if referrer:
            refs = referrer.get("referrals", [])
            if referee_id not in refs:
                refs.append(referee_id)
                self.update_user(referrer_id, {"referrals": refs})

    def add_pending_payment(self, user_id, code, amount):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO pending_payments (user_id, code, amount, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, code, amount, datetime.now().isoformat()))
            conn.commit()
        return True
