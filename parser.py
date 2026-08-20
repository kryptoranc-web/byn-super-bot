import aiohttp
import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
from config import SOURCES, BANKS

class CurrencyParser:
    def __init__(self):
        self.data = {
            "usd": {"buy": 0, "sell": 0, "nbrb": 0},
            "eur": {"buy": 0, "sell": 0, "nbrb": 0}
        }
        self.banks_data = []
        self.last_update = None

    async def get_nbrb_rates(self):
        """Получение официальных курсов НБРБ"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SOURCES["nbrb"] + "?periodicity=0") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data:
                            if item["Cur_Abbreviation"] in ["USD", "EUR"]:
                                self.data[item["Cur_Abbreviation"].lower()]["nbrb"] = item["Cur_OfficialRate"]
                        return True
        except Exception as e:
            print(f"Ошибка НБРБ: {e}")
            return False

    async def get_bank_rates(self):
        """Парсинг курсов банков с myfin.by"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SOURCES["myfin"]) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        # Тут будет реальный парсинг myfin
                        # Сейчас имитация для демонстрации
                        self.banks_data = []
                        for bank in BANKS:
                            self.banks_data.append({
                                "bank": bank,
                                "usd_buy": round(2.95 + (len(self.banks_data) * 0.01), 4),
                                "usd_sell": round(3.05 + (len(self.banks_data) * 0.01), 4),
                                "eur_buy": round(3.40 + (len(self.banks_data) * 0.01), 4),
                                "eur_sell": round(3.50 + (len(self.banks_data) * 0.01), 4),
                                "address": f"г. Минск, ул. Примерная, {len(self.banks_data) + 1}"
                            })
                        self.last_update = datetime.now()
                        return True
        except Exception as e:
            print(f"Ошибка myfin: {e}")
            return False

    async def get_forex_data(self):
        """Получение данных с Forex (имитация)"""
        # В реальном проекте здесь API для Forex
        return {
            "dxy": 104.5,
            "usd_rub": 89.50,
            "eur_usd": 1.0850,
            "brent": 85.0
                  }
