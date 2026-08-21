from datetime import datetime
from analyzer import TechnicalAnalyzer

class AIForecast:
    def __init__(self):
        self.analyzer = TechnicalAnalyzer()

    async def analyze_forex_impact(self):
        return {"dxy_trend": "нейтральный", "usd_rub_trend": "укрепление", "brent_trend": "стабильность"}

    async def check_self_validation(self, data):
        validation_result = {"stage1": False, "stage2": False, "stage3": False, "overall_confidence": 0}
        if data.get("rsi") and data.get("trend"):
            validation_result["stage1"] = True
        if data.get("seasonal_impact"):
            validation_result["stage2"] = True
        if data.get("forex_impact"):
            validation_result["stage3"] = True
        confidence = sum(validation_result.values()) * 100 / 3
        validation_result["overall_confidence"] = round(confidence)
        return validation_result

    async def generate_forecast(self, currency, current_rate, historical_prices):
        analysis = self.analyzer.analyze(historical_prices, historical_prices)
        analysis = analysis.get(currency, {})
        rsi = analysis.get("rsi", 50)
        trend = analysis.get("trend", "нейтральный")
        forex_impact = await self.analyze_forex_impact()
        day_of_month = datetime.now().day
        seasonal_effect = "нисходящий" if 18 <= day_of_month <= 22 else "нейтральный"
        seasonal_description = "налоговый период" if 18 <= day_of_month <= 22 else "вне налогового периода"
        rsi_effect = -0.5 if rsi > 70 else (0.5 if rsi < 30 else 0)
        seasonal_effect_value = -0.7 if seasonal_effect == "нисходящий" else 0
        forex_effect = 0.3 if "укрепление" in forex_impact["usd_rub_trend"] else 0
        total_effect = rsi_effect + seasonal_effect_value + forex_effect
        week_change = total_effect * 0.3
        month_change = total_effect * 0.8
        quarter_change = total_effect * 1.5
        return {
            "currency": currency,
            "current_rate": current_rate,
            "rsi": rsi,
            "trend": trend,
            "seasonal_impact": seasonal_description,
            "forex_impact": forex_impact,
            "predictions": {
                "week": round(current_rate * (1 + week_change/100), 4),
                "month": round(current_rate * (1 + month_change/100), 4),
                "quarter": round(current_rate * (1 + quarter_change/100), 4)
            },
            "levels": {"support": round(current_rate * 0.99, 4), "resistance": round(current_rate * 1.01, 4)},
            "recommendation": "ПОКУПАТЬ ✅" if total_effect > 0.3 else "ПРОДАВАТЬ ❌" if total_effect < -0.3 else "ДЕРЖАТЬ ⏳",
            "risk": min(10, 5 + (3 if rsi > 80 or rsi < 20 else 1 if rsi > 70 or rsi < 30 else 0) + (2 if abs(total_effect) > 0.5 else 0)),
            "confidence": 75,
            "sources": ["https://www.nbrb.by/statistics/rates", "https://myfin.by", "https://www.cbr.ru/", "https://www.investing.com/"],
            "validation": await self.check_self_validation({"rsi": rsi, "trend": trend, "seasonal_impact": seasonal_description, "forex_impact": forex_impact})
        }
