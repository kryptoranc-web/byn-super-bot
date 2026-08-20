# Топ-10 банков Минска для отслеживания
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

# Валюты для отслеживания
CURRENCIES = ["USD", "EUR"]

# Источники данных
SOURCES = {
    "nbrb": "https://api.nbrb.by/exrates/rates",
    "myfin": "https://myfin.by",
    "cbr": "https://www.cbr.ru/scripts/XML_daily.asp"
}

# Часы уведомлений (9:00 - 22:00)
NOTIFICATION_HOURS = list(range(9, 23))

# Настройки AI-анализа
AI_SETTINGS = {
    "rsi_period": 14,
    "ma_fast": 20,
    "ma_slow": 50,
    "ma_trend": 200
}
