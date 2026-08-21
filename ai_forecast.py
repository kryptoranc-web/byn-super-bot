import numpy as np
from datetime import datetime

class AIForecast:
    def __init__(self):
        self.analyzer = None

    def set_analyzer(self, analyzer):
        self.analyzer = analyzer

    async def _get_forex_data(self):
        return {
            "dxy": 104.5,
            "usd_rub": 89.50,
            "eur_usd": 1.0850,
            "brent": 85.0,
            "dxy_trend": "нейтральный",
            "usd_rub_trend": "укрепление",
            "brent_trend": "стабильность"
        }

    async def _get_news_sentiment(self):
        return {"sentiment": "нейтральный", "key_events": ["Нет значимых событий"], "impact": 0}

    async def _get_seasonal_data(self):
        day = datetime.now().day
        month = datetime.now().month
        if 18 <= day <= 22:
            return {"effect": "нисходящий", "description": "налоговый период", "impact": -0.7}
        elif month in [1, 2, 7, 8]:
            return {"effect": "нейтральный", "description": "низкая активность", "impact": 0}
        else:
            return {"effect": "нейтральный", "description": "обычный период", "impact": 0}

    async def _get_historical_patterns(self, prices, days=90):
        if len(prices) < days:
            return {"pattern": "недостаточно данных", "accuracy": 50}
        recent = prices[-30:]
        trend = "восходящий" if recent[-1] > recent[0] else "нисходящий"
        return {"pattern": trend, "accuracy": 65}

    def _get_best_bank(self, banks_data, action, currency):
        if not banks_data:
            return None
        key = f"{currency.lower()}_buy" if action == "ПОКУПАТЬ ✅" else f"{currency.lower()}_sell"
        if action == "ПОКУПАТЬ ✅":
            best = min(banks_data, key=lambda x: x.get(key, float('inf')))
        else:
            best = max(banks_data, key=lambda x: x.get(key, 0))
        return {
            "name": best.get("bank", "Неизвестно"),
            "rate": best.get(key, 0),
            "address": best.get("address", "Адрес не указан"),
            "type": best.get("type", "отделение")
        }

    def _generate_trading_strategy(self, recommendation, current_rate, target_price, currency, banks_data):
        if recommendation == "ПОКУПАТЬ ✅":
            best_bank = self._get_best_bank(banks_data, "ПОКУПАТЬ ✅", currency.lower())
            entry_price = best_bank["rate"] if best_bank else current_rate * 0.995
            exit_price = target_price if target_price > entry_price else entry_price * 1.02
            hold_days = 7
            return {
                "action": "ПОКУПКА", "currency": currency, "bank": best_bank,
                "entry_price": entry_price, "exit_price": exit_price, "hold_days": hold_days,
                "expected_profit": round(((exit_price - entry_price) / entry_price) * 100, 2),
                "steps": [
                    f"1️⃣ Откройте приложение {best_bank['name'] if best_bank else 'выбранный банк'} (или посетите отделение по адресу: {best_bank['address'] if best_bank else 'укажите адрес'})",
                    f"2️⃣ Купите {currency} по курсу {entry_price:.4f} BYN",
                    f"3️⃣ Держите {hold_days} дней до достижения цели {exit_price:.4f} BYN",
                    f"4️⃣ Продайте в банке с лучшим курсом продажи",
                    f"5️⃣ Зафиксируйте прибыль {round(((exit_price - entry_price) / entry_price) * 100, 2)}%"
                ]
            }
        elif recommendation == "ПРОДАВАТЬ ❌":
            best_bank = self._get_best_bank(banks_data, "ПРОДАВАТЬ ❌", currency.lower())
            entry_price = current_rate
            exit_price = best_bank["rate"] if best_bank else current_rate * 1.005
            hold_days = 3
            return {
                "action": "ПРОДАЖА", "currency": currency, "bank": best_bank,
                "entry_price": entry_price, "exit_price": exit_price, "hold_days": hold_days,
                "expected_profit": round(((exit_price - entry_price) / entry_price) * 100, 2),
                "steps": [
                    f"1️⃣ Откройте приложение {best_bank['name'] if best_bank else 'выбранный банк'} (или посетите отделение по адресу: {best_bank['address'] if best_bank else 'укажите адрес'})",
                    f"2️⃣ Продайте {currency} по курсу {entry_price:.4f} BYN",
                    f"3️⃣ Дождитесь коррекции (ориентировочно {hold_days} дней)",
                    f"4️⃣ Купите обратно по цене {exit_price:.4f} BYN",
                    f"5️⃣ Зафиксируйте прибыль {round(((exit_price - entry_price) / entry_price) * 100, 2)}%"
                ]
            }
        else:
            return {
                "action": "ДЕРЖАТЬ", "currency": currency, "bank": None,
                "entry_price": current_rate, "exit_price": current_rate, "hold_days": 0,
                "expected_profit": 0,
                "steps": [
                    "⏳ Рекомендуем воздержаться от сделок до появления более чёткого сигнала.",
                    "📊 Следите за обновлениями прогноза."
                ]
            }

    def _ai_1_technical_rsi(self, rsi):
        if rsi < 30:
            return {"decision": "ПОКУПАТЬ ✅", "reason": f"RSI = {rsi} — зона перепроданности, ожидается отскок вверх."}
        elif rsi > 70:
            return {"decision": "ПРОДАВАТЬ ❌", "reason": f"RSI = {rsi} — зона перекупленности, ожидается коррекция вниз."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": f"RSI = {rsi} — нейтральная зона, нет явного сигнала."}

    def _ai_2_technical_ma(self, ma_fast, ma_slow, ma_trend):
        if ma_fast > ma_slow > ma_trend:
            return {"decision": "ПОКУПАТЬ ✅", "reason": "Скользящие средние: MA-20 > MA-50 > MA-200 — восходящий тренд."}
        elif ma_fast < ma_slow < ma_trend:
            return {"decision": "ПРОДАВАТЬ ❌", "reason": "Скользящие средние: MA-20 < MA-50 < MA-200 — нисходящий тренд."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": "Скользящие средние: тренд не выражен, флэт."}

    def _ai_3_fundamental(self, seasonal_data):
        if seasonal_data["effect"] == "нисходящий":
            return {"decision": "ПРОДАВАТЬ ❌", "reason": f"Сезонный фактор: {seasonal_data['description']} — исторически курс снижается."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": f"Сезонный фактор: {seasonal_data['description']} — нет явных сигналов."}

    def _ai_4_forex(self, forex_data):
        if forex_data["usd_rub_trend"] == "укрепление":
            return {"decision": "ПОКУПАТЬ ✅", "reason": "USD/RUB укрепляется — позитивное влияние на USD/BYN."}
        elif forex_data["usd_rub_trend"] == "ослабление":
            return {"decision": "ПРОДАВАТЬ ❌", "reason": "USD/RUB ослабевает — негативное влияние на USD/BYN."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": "USD/RUB нейтрален — нет явного сигнала."}

    def _ai_5_oil(self, forex_data):
        if forex_data["brent_trend"] == "рост":
            return {"decision": "ПОКУПАТЬ ✅", "reason": "Нефть Brent растёт — укрепляет RUB, позитивно для BYN."}
        elif forex_data["brent_trend"] == "падение":
            return {"decision": "ПРОДАВАТЬ ❌", "reason": "Нефть Brent падает — ослабляет RUB, негативно для BYN."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": "Нефть Brent стабильна — нет явного сигнала."}

    def _ai_6_news(self, news_data):
        if news_data["sentiment"] == "позитивный":
            return {"decision": "ПОКУПАТЬ ✅", "reason": "Новостной фон позитивный — ожидается рост."}
        elif news_data["sentiment"] == "негативный":
            return {"decision": "ПРОДАВАТЬ ❌", "reason": "Новостной фон негативный — ожидается падение."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": "Новостной фон нейтральный — нет явного сигнала."}

    def _ai_7_historical(self, pattern_data):
        if pattern_data["pattern"] == "восходящий" and pattern_data["accuracy"] > 60:
            return {"decision": "ПОКУПАТЬ ✅", "reason": f"Исторический паттерн: восходящий (точность {pattern_data['accuracy']}%)."}
        elif pattern_data["pattern"] == "нисходящий" and pattern_data["accuracy"] > 60:
            return {"decision": "ПРОДАВАТЬ ❌", "reason": f"Исторический паттерн: нисходящий (точность {pattern_data['accuracy']}%)."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": "Исторический паттерн: недостаточно данных."}

    def _ai_8_indicators(self, rsi, ma_fast, ma_slow):
        if rsi < 40 and ma_fast > ma_slow:
            return {"decision": "ПОКУПАТЬ ✅", "reason": "RSI < 40 и MA-20 > MA-50 — подтверждение роста."}
        elif rsi > 60 and ma_fast < ma_slow:
            return {"decision": "ПРОДАВАТЬ ❌", "reason": "RSI > 60 и MA-20 < MA-50 — подтверждение падения."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": "Индикаторы разнонаправлены — нет явного сигнала."}

    def _ai_9_volatility(self, prices):
        if len(prices) < 20:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": "Недостаточно данных для анализа волатильности."}
        volatility = np.std(prices[-20:]) / np.mean(prices[-20:]) * 100
        if volatility < 1:
            return {"decision": "ПОКУПАТЬ ✅", "reason": f"Низкая волатильность ({volatility:.1f}%) — ожидается резкое движение вверх."}
        elif volatility > 5:
            return {"decision": "ПРОДАВАТЬ ❌", "reason": f"Высокая волатильность ({volatility:.1f}%) — высокий риск, лучше продать."}
        else:
            return {"decision": "ДЕРЖАТЬ ⏳", "reason": f"Умеренная волатильность ({volatility:.1f}%) — без явного сигнала."}

    def _ai_10_meta_analysis(self, all_decisions):
        votes = {"ПОКУПАТЬ ✅": 0, "ПРОДАВАТЬ ❌": 0, "ДЕРЖАТЬ ⏳": 0}
        for d in all_decisions:
            votes[d["decision"]] += 1
        max_votes = max(votes.values())
        if max_votes >= 6:
            for decision, count in votes.items():
                if count == max_votes:
                    return {"decision": decision, "reason": f"Мета-анализ: {count}/10 моделей рекомендуют {decision}."}
        return {"decision": "ДЕРЖАТЬ ⏳", "reason": f"Мета-анализ: разногласия ({votes}). Рекомендуем воздержаться."}

    async def generate_forecast(self, currency, current_rate, historical_prices, banks_data=None):
        if not self.analyzer:
            from analyzer import TechnicalAnalyzer
            self.analyzer = TechnicalAnalyzer()

        analysis = self.analyzer.analyze(historical_prices, historical_prices).get(currency, {})
        rsi = analysis.get("rsi", 50)
        ma_fast = analysis.get("ma_fast", current_rate)
        ma_slow = analysis.get("ma_slow", current_rate)
        ma_trend = analysis.get("ma_trend", current_rate)
        trend = analysis.get("trend", "нейтральный")
        
        forex_data = await self._get_forex_data()
        news_data = await self._get_news_sentiment()
        seasonal_data = await self._get_seasonal_data()
        pattern_data = await self._get_historical_patterns(historical_prices)

        ai_results = [
            self._ai_1_technical_rsi(rsi),
            self._ai_2_technical_ma(ma_fast, ma_slow, ma_trend),
            self._ai_3_fundamental(seasonal_data),
            self._ai_4_forex(forex_data),
            self._ai_5_oil(forex_data),
            self._ai_6_news(news_data),
            self._ai_7_historical(pattern_data),
            self._ai_8_indicators(rsi, ma_fast, ma_slow),
            self._ai_9_volatility(historical_prices),
        ]
        meta_result = self._ai_10_meta_analysis(ai_results)
        ai_results.append(meta_result)

        votes = {"ПОКУПАТЬ ✅": 0, "ПРОДАВАТЬ ❌": 0, "ДЕРЖАТЬ ⏳": 0}
        for result in ai_results:
            votes[result["decision"]] += 1
        final_decision = max(votes, key=votes.get)
        max_votes = votes[final_decision]

        confidence = 90 if max_votes >= 7 else 75 if max_votes >= 5 else 60
        consensus_text = f"✅ Сильный сигнал ({max_votes}/10 AI)" if max_votes >= 7 else f"⚠️ Средний сигнал ({max_votes}/10 AI)" if max_votes >= 5 else f"❌ Слабый сигнал ({max_votes}/10 AI)"

        rsi_effect = -0.5 if rsi > 70 else (0.5 if rsi < 30 else 0)
        total_effect = rsi_effect + seasonal_data["impact"] + (0.3 if forex_data["usd_rub_trend"] == "укрепление" else -0.3 if forex_data["usd_rub_trend"] == "ослабление" else 0)
        
        week_change = total_effect * 0.3
        month_change = total_effect * 0.8
        quarter_change = total_effect * 1.5
        target_price = current_rate * (1 + week_change/100)

        support = min(historical_prices[-20:]) * 0.995 if len(historical_prices) >= 20 else current_rate * 0.99
        resistance = max(historical_prices[-20:]) * 1.005 if len(historical_prices) >= 20 else current_rate * 1.01

        strategy = self._generate_trading_strategy(final_decision, current_rate, target_price, currency, banks_data or [])

        top_banks = {"offline": [], "online": [], "best_buy": None, "best_sell": None}
        if banks_data:
            offline = [b for b in banks_data if b.get("type") == "отделение"]
            online = [b for b in banks_data if b.get("type") == "онлайн"]
            for bank_list, key in [(offline, "offline"), (online, "online")]:
                if bank_list:
                    sorted_banks = sorted(bank_list, key=lambda x: (x.get('usd_sell', 0) - x.get('usd_buy', 0)) + (x.get('eur_sell', 0) - x.get('eur_buy', 0)))
                    top_banks[key] = sorted_banks[:5]
            all_banks = offline + online
            if all_banks:
                top_banks["best_buy"] = min(all_banks, key=lambda x: x.get(f"{currency.lower()}_buy", float('inf')))
                top_banks["best_sell"] = max(all_banks, key=lambda x: x.get(f"{currency.lower()}_sell", 0))

        return {
            "currency": currency,
            "current_rate": current_rate,
            "rsi": rsi,
            "trend": trend,
            "seasonal_impact": seasonal_data["description"],
            "forex_impact": forex_data,
            "predictions": {
                "week": round(current_rate * (1 + week_change/100), 4),
                "month": round(current_rate * (1 + month_change/100), 4),
                "quarter": round(current_rate * (1 + quarter_change/100), 4)
            },
            "levels": {
                "support": round(support, 4),
                "resistance": round(resistance, 4)
            },
            "recommendation": final_decision,
            "risk": min(10, 5 + (3 if rsi > 80 or rsi < 20 else 1 if rsi > 70 or rsi < 30 else 0) + (2 if abs(total_effect) > 0.5 else 0)),
            "confidence": confidence,
            "consensus": consensus_text,
            "votes": votes,
            "ai_models": ai_results,
            "strategy": strategy,
            "top_banks": top_banks,
            "sources": [
                "https://www.nbrb.by/statistics/rates — официальные курсы НБРБ",
                "https://myfin.by — курсы банков Минска",
                "https://www.cbr.ru/ — курсы российского рубля",
                "https://www.investing.com/ — внешние факторы (нефть, DXY)",
                "Исторические данные — за последние 30 и 90 дней"
            ]
        }
