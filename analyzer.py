import numpy as np
from config import AI_SETTINGS

class TechnicalAnalyzer:
    def __init__(self):
        self.rsi_period = AI_SETTINGS["rsi_period"]
        self.ma_fast = AI_SETTINGS["ma_fast"]
        self.ma_slow = AI_SETTINGS["ma_slow"]
        self.ma_trend = AI_SETTINGS["ma_trend"]

    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        if down == 0:
            return 100
        rs = up / down
        rsi = 100 - (100 / (1 + rs))
        for i in range(period + 1, len(deltas)):
            delta = deltas[i]
            upval = delta if delta > 0 else 0
            downval = -delta if delta < 0 else 0
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down
            rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def calculate_ma(self, prices, period):
        if len(prices) < period:
            return prices[-1]
        return round(sum(prices[-period:]) / period, 4)

    def get_support_resistance(self, prices):
        if len(prices) < 20:
            return {"support": round(prices[-1] * 0.98, 4), "resistance": round(prices[-1] * 1.02, 4)}
        recent = prices[-20:]
        return {"support": round(min(recent) * 0.995, 4), "resistance": round(max(recent) * 1.005, 4)}

    def analyze(self, prices_usd, prices_eur):
        result = {}
        for currency, prices in [("USD", prices_usd), ("EUR", prices_eur)]:
            if len(prices) < 30:
                result[currency] = {"rsi": 50, "ma_fast": prices[-1], "ma_slow": prices[-1], "ma_trend": prices[-1], "trend": "недостаточно данных", "levels": {"support": prices[-1] * 0.98, "resistance": prices[-1] * 1.02}}
                continue
            rsi = self.calculate_rsi(prices)
            ma_fast = self.calculate_ma(prices, self.ma_fast)
            ma_slow = self.calculate_ma(prices, self.ma_slow)
            ma_trend = self.calculate_ma(prices, self.ma_trend)
            levels = self.get_support_resistance(prices)
            if ma_fast > ma_slow > ma_trend:
                trend = "восходящий 📈"
            elif ma_fast < ma_slow < ma_trend:
                trend = "нисходящий 📉"
            else:
                trend = "флэт ↔️"
            result[currency] = {"rsi": rsi, "ma_fast": ma_fast, "ma_slow": ma_slow, "ma_trend": ma_trend, "trend": trend, "levels": levels}
        return result
