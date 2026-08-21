import random
import string

# ============================================================
# ВАШИ ПЛАТЁЖНЫЕ РЕКВИЗИТЫ (уже вставлены)
# ============================================================
RECEIVER_CARD = "9112388018709761"                         # ✅ Ваша карта
RECEIVER_IBAN = "BY40BPSB3014R000000000009680"            # ✅ Ваш IBAN
RECEIVER_BANK = "Сбер Банк"
PAYMENT_PURPOSE = "Ежемесячная подписка на сервис BYN Super Investor Bot"
SUBSCRIPTION_PRICE = "29.90 BYN"

def generate_erip_payment(user_id, amount=SUBSCRIPTION_PRICE):
    payment_id = ''.join(random.choices(string.digits, k=10))
    return {
        "payment_id": payment_id,
        "amount": amount,
        "receiver_card": RECEIVER_CARD,
        "receiver_iban": RECEIVER_IBAN,
        "receiver_bank": RECEIVER_BANK,
        "purpose": PAYMENT_PURPOSE,
        "account": user_id,
        "erip_link": f"https://e-pay.by/service/placeholder_{payment_id}"
    }

def confirm_payment(payment_id):
    return True
