"""Explainable, historical risk metrics for existing holdings.

The service intentionally reports historical frequencies rather than forecasting or
recommending trades.  Results are cached because upstream historical sources may
be slow or temporarily unavailable.
"""
from __future__ import annotations

import math
import statistics
import time
from datetime import date, timedelta
from threading import Lock


class RiskDataUnavailable(RuntimeError):
    pass


class RiskService:
    CACHE_SECONDS = 6 * 60 * 60
    HORIZON_DAYS = 5
    DOWNSIDE_THRESHOLD = -0.05

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, dict[str, object]]] = {}
        self._lock = Lock()

    def assess(self, symbol: str, name: str) -> dict[str, object]:
        symbol = symbol.strip().upper()
        with self._lock:
            cached = self._cache.get(symbol)
            if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
                return {**cached[1], "name": name}

        closes, as_of = self._closes(symbol)
        if len(closes) < 65:
            raise RiskDataUnavailable("历史价格样本不足，暂无法生成风险评估。")

        daily_returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
        forward_returns = [
            closes[index + self.HORIZON_DAYS] / closes[index] - 1
            for index in range(len(closes) - self.HORIZON_DAYS)
        ]
        downside_count = sum(value <= self.DOWNSIDE_THRESHOLD for value in forward_returns)
        downside_probability = round(downside_count / len(forward_returns) * 100, 1)
        annualized_volatility = round(statistics.stdev(daily_returns) * math.sqrt(252) * 100, 1)
        risk_level = "高" if downside_probability >= 20 or annualized_volatility >= 50 else "中" if downside_probability >= 8 or annualized_volatility >= 30 else "低"
        confidence = "高" if len(forward_returns) >= 180 else "中" if len(forward_returns) >= 90 else "低"
        item: dict[str, object] = {
            "symbol": symbol,
            "name": name,
            "horizon_trading_days": self.HORIZON_DAYS,
            "downside_threshold_percent": abs(self.DOWNSIDE_THRESHOLD) * 100,
            "historical_downside_probability": downside_probability,
            "annualized_volatility_percent": annualized_volatility,
            "risk_level": risk_level,
            "confidence": confidence,
            "sample_count": len(forward_returns),
            "as_of": as_of,
            "explanation": f"历史样本中，未来 {self.HORIZON_DAYS} 个交易日累计跌幅达到 {abs(self.DOWNSIDE_THRESHOLD) * 100:.0f}% 或以上的比例。",
        }
        with self._lock:
            self._cache[symbol] = (time.monotonic(), item)
        return item

    def _closes(self, symbol: str) -> tuple[list[float], str]:
        try:
            import akshare as ak
        except ImportError as error:
            raise RiskDataUnavailable("未安装历史行情依赖。") from error
        try:
            if len(symbol) == 5 and symbol.isdigit():
                frame = ak.stock_hk_daily(symbol=symbol)
                values = frame["close"].dropna().tolist()
                as_of = str(frame["date"].iloc[-1])
            else:
                start = (date.today() - timedelta(days=730)).strftime("%Y%m%d")
                end = date.today().strftime("%Y%m%d")
                frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
                values = frame["收盘"].dropna().tolist()
                as_of = str(frame["日期"].iloc[-1])
        except Exception as error:
            raise RiskDataUnavailable("历史行情源暂时不可用，请稍后刷新。") from error
        return [float(value) for value in values], as_of
