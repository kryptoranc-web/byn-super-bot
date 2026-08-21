import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from config import SOURCES, BANKS, CITIES

class CurrencyParser:
    def __init__(self):
        self.data = {"usd": {"nbrb": 0}, "eur": {"nbrb": 0}}
        self.banks_data = {}
        self.last_update = None

    async def get_nbrb_rates(self):
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

    async def get_bank_rates_for_city(self, city="Минск"):
        try:
            city_slug = city.lower().replace(" ", "_")
            url = f"{SOURCES['myfin']}/bank-ratings/{city_slug}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        table = soup.find('table', class_='table')
                        if not table:
                            return False
                        rows = table.find_all('tr')[1:11]
                        banks_list = []
                        for row in rows:
                            cols = row.find_all('td')
                            if len(cols) < 5:
                                continue
                            banks_list.append({
                                "bank": cols[0].text.strip(),
                                "usd_buy": float(cols[1].text.replace(',', '.')),
                                "usd_sell": float(cols[2].text.replace(',', '.')),
                                "eur_buy": float(cols[3].text.replace(',', '.')),
                                "eur_sell": float(cols[4].text.replace(',', '.')),
                                "address": f"г. {city}, ул. Примерная, 1",
                                "city": city
                            })
                        self.banks_data[city] = banks_list
                        self.last_update = datetime.now()
                        return True
        except Exception as e:
            print(f"Ошибка myfin для {city}: {e}")
            return False

    async def get_forex_data(self):
        return {"dxy": 104.5, "usd_rub": 89.50, "eur_usd": 1.0850, "brent": 85.0}
