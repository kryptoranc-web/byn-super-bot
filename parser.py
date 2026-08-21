import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from config import SOURCES, BANKS, CITIES

class CurrencyParser:
    def __init__(self):
        self.data = {
            "usd": {"buy": 0, "sell": 0, "nbrb": 0},
            "eur": {"buy": 0, "sell": 0, "nbrb": 0}
        }
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
                        
                        tables = soup.find_all('table', class_='table')
                        banks_list = []
                        
                        for table in tables:
                            rows = table.find_all('tr')[1:11]
                            is_online = "онлайн" in table.get_text().lower()
                            
                            for row in rows:
                                cols = row.find_all('td')
                                if len(cols) < 5:
                                    continue
                                
                                bank_name = cols[0].text.strip()
                                usd_buy = float(cols[1].text.replace(',', '.'))
                                usd_sell = float(cols[2].text.replace(',', '.'))
                                eur_buy = float(cols[3].text.replace(',', '.'))
                                eur_sell = float(cols[4].text.replace(',', '.'))
                                
                                address = await self._get_bank_address(bank_name, city)
                                
                                banks_list.append({
                                    "bank": bank_name,
                                    "usd_buy": usd_buy,
                                    "usd_sell": usd_sell,
                                    "eur_buy": eur_buy,
                                    "eur_sell": eur_sell,
                                    "address": address,
                                    "city": city,
                                    "type": "онлайн" if is_online else "отделение"
                                })
                        
                        offline = [b for b in banks_list if b["type"] == "отделение"]
                        online = [b for b in banks_list if b["type"] == "онлайн"]
                        
                        self.banks_data[city] = {
                            "offline": offline[:10],
                            "online": online[:10],
                            "all": banks_list
                        }
                        self.last_update = datetime.now()
                        return True
        except Exception as e:
            print(f"Ошибка myfin для {city}: {e}")
            return False

    async def _get_bank_address(self, bank_name, city):
        try:
            async with aiohttp.ClientSession() as session:
                city_slug = city.lower().replace(" ", "_")
                url = f"{SOURCES['myfin']}/bank-ratings/{city_slug}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        return f"г. {city}, ул. Примерная, 1"
        except:
            pass
        return f"г. {city}, ул. Примерная, 1"

    async def get_forex_data(self):
        return {
            "dxy": 104.5,
            "usd_rub": 89.50,
            "eur_usd": 1.0850,
            "brent": 85.0
                                }
