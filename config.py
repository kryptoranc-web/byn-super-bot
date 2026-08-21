# # Топ-10 банков (для парсинга)
BANKS = [
    "Сбербанк",
    "МТБанк",
    "Беларусбанк",
    "Приорбанк",
    "БПС-Сбербанк",
    "Банк Дабрабыт",
    "Белинвестбанк",
    "Альфа-Банк",
    "Паритетбанк",
    "БНБ-Банк"
]

# Города Беларуси
CITIES = [
    "Минск",
    "Брест",
    "Витебск",
    "Гомель",
    "Гродно",
    "Могилёв",
    "Барановичи",
    "Борисов",
    "Лида",
    "Мозырь",
    "Новополоцк",
    "Пинск",
    "Полоцк",
    "Речица",
    "Слуцк",
    "Солигорск",
    "Орша"
]

CURRENCIES = ["USD", "EUR"]

SOURCES = {
    "nbrb": "https://api.nbrb.by/exrates/rates",
    "myfin": "https://myfin.by",
    "cbr": "https://www.cbr.ru/scripts/XML_daily.asp"
}

NOTIFICATION_HOURS = list(range(9, 23))

AI_SETTINGS = {
    "rsi_period": 14,
    "ma_fast": 20,
    "ma_slow": 50,
    "ma_trend": 200
}

# Подписка
TRIAL_DAYS = 14
SUBSCRIPTION_PRICE = "29.90 BYN"
MAX_BONUS_DAYS_PER_MONTH = 30
ADMIN_ID = 123456789  # ЗАМЕНИТЕ НА ВАШ IDТоп-10 банков Минска для отслеживания

