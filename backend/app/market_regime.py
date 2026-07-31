"""Daily market-regime context for swing reviews; not intraday execution data."""
from __future__ import annotations

import time


class MarketRegimeService:
    CACHE_SECONDS = 30 * 60
    A_INDEXES = (("sh000001", "上证综指"), ("sh000300", "沪深300"), ("sz399006", "创业板指"))

    def __init__(self, fetcher=None) -> None:
        self._fetcher = fetcher or self._akshare_fetch
        self._cached = None

    @staticmethod
    def _akshare_fetch(symbol: str):
        import akshare as ak
        return ak.stock_zh_index_daily(symbol=symbol)

    def assess(self) -> dict[str, object]:
        if self._cached and time.monotonic() - self._cached[0] < self.CACHE_SECONDS:
            return self._cached[1]
        indexes = []
        try:
            for symbol, name in self.A_INDEXES:
                frame = self._fetcher(symbol)
                if frame is None or len(frame.index) < 60:
                    continue
                close = [float(value) for value in frame["close"].tolist()]
                latest, sma20, sma60 = close[-1], sum(close[-20:]) / 20, sum(close[-60:]) / 60
                five_day = (latest / close[-6] - 1) * 100
                indexes.append({"symbol": symbol, "name": name, "five_day_return_percent": round(five_day, 2), "trend": "up" if sma20 >= sma60 else "down", "above_sma20": latest >= sma20})
            if not indexes:
                raise ValueError("no usable index history")
            score = sum((1 if item["trend"] == "up" else -1) + (1 if item["above_sma20"] else -1) for item in indexes)
            regime = "supportive" if score >= 3 else "defensive" if score <= -3 else "mixed"
            result = {"status": "ready", "regime": regime, "indexes": indexes, "source": "AKShare 指数日线", "note": "基于宽基日线趋势与近5日表现的波段环境参考；未覆盖行业相对强弱、市场广度或盘中资金。"}
        except Exception as error:
            result = {"status": "unavailable", "regime": "unknown", "indexes": [], "source": "AKShare", "note": f"市场环境暂不可用：{error}"}
        self._cached = (time.monotonic(), result)
        return result
