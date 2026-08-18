"""Daily market-regime context for swing reviews; never cross market boundaries."""
from __future__ import annotations

import time

from app.market_adapter import adapter_for_market


LEGACY_CN_INDEX_SYMBOLS = {"sh000001", "sh000300", "sz399006"}


def regime_market(value: dict[str, object] | None) -> str | None:
    """Return the market identity carried by a regime payload.

    Pre-v3 MarketRegimeService was A-share only and did not persist ``market``.
    Recognize only that narrow legacy shape as CN; never reinterpret a missing
    market as matching HK/US.
    """
    if not value:
        return None
    explicit = str(value.get("market") or "").strip().upper()
    if explicit:
        return explicit
    indexes = value.get("indexes") or []
    symbols = {
        str(item.get("symbol") or "").strip()
        for item in indexes
        if isinstance(item, dict) and item.get("symbol")
    }
    if symbols and symbols.issubset(LEGACY_CN_INDEX_SYMBOLS):
        return "CN"
    source = str(value.get("source") or "")
    if source.startswith("AKShare"):
        return "CN"
    return None


def regime_matches_market(value: dict[str, object] | None, market: str | None) -> bool:
    expected = str(market or "").strip().upper()
    return bool(expected and regime_market(value) == expected)


class MarketRegimeService:
    CACHE_SECONDS = 30 * 60
    A_INDEXES = (("sh000001", "上证综指"), ("sh000300", "沪深300"), ("sz399006", "创业板指"))
    INDEXES_BY_MARKET = {"CN": A_INDEXES}

    def __init__(self, fetcher=None) -> None:
        self._fetcher = fetcher or self._akshare_fetch
        self._cached: dict[str, tuple[float, dict[str, object]]] = {}

    @staticmethod
    def _akshare_fetch(symbol: str):
        import akshare as ak
        return ak.stock_zh_index_daily(symbol=symbol)

    def assess(self, market: str = "CN") -> dict[str, object]:
        """Assess only benchmarks that belong to ``market``.

        The built-in provider currently has a verified A-share index path only.
        HK/US therefore return an explicit unavailable state until a dedicated
        provider adapter is configured; they must never fall back to CN indexes.
        """
        normalized = str(market or "").strip().upper()
        adapter = adapter_for_market(normalized)
        if adapter is None:
            return {
                "status": "unavailable",
                "regime": "unknown",
                "market": normalized or None,
                "indexes": [],
                "benchmark_symbols": [],
                "source": "unconfigured",
                "note": "未知市场，未生成市场环境。",
            }
        configured_indexes = self.INDEXES_BY_MARKET.get(normalized)
        if not configured_indexes:
            return {
                "status": "unavailable",
                "regime": "unknown",
                "market": normalized,
                "indexes": [],
                "benchmark_symbols": list(adapter.benchmark_symbols),
                "source": "unconfigured",
                "note": f"{normalized} 市场尚未配置经验证的宽基日线适配器；不会回退到其他市场指数。",
            }

        cached = self._cached.get(normalized)
        if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
            return cached[1]

        indexes = []
        try:
            for symbol, name in configured_indexes:
                frame = self._fetcher(symbol)
                if frame is None or len(frame.index) < 60:
                    continue
                close = [float(value) for value in frame["close"].tolist()]
                latest, sma20, sma60 = close[-1], sum(close[-20:]) / 20, sum(close[-60:]) / 60
                five_day = (latest / close[-6] - 1) * 100
                indexes.append({
                    "symbol": symbol,
                    "name": name,
                    "five_day_return_percent": round(five_day, 2),
                    "trend": "up" if sma20 >= sma60 else "down",
                    "above_sma20": latest >= sma20,
                })
            if not indexes:
                raise ValueError("no usable index history")
            score = sum(
                (1 if item["trend"] == "up" else -1)
                + (1 if item["above_sma20"] else -1)
                for item in indexes
            )
            regime = "supportive" if score >= 3 else "defensive" if score <= -3 else "mixed"
            result = {
                "status": "ready",
                "regime": regime,
                "market": normalized,
                "indexes": indexes,
                "benchmark_symbols": list(adapter.benchmark_symbols),
                "source": "AKShare 指数日线",
                "note": "基于同市场宽基日线趋势与近5日表现的波段环境参考；未覆盖行业相对强弱、市场广度或盘中资金。",
            }
        except Exception as error:
            result = {
                "status": "unavailable",
                "regime": "unknown",
                "market": normalized,
                "indexes": [],
                "benchmark_symbols": list(adapter.benchmark_symbols),
                "source": "AKShare",
                "note": f"{normalized} 市场环境暂不可用：{error}",
            }
        self._cached[normalized] = (time.monotonic(), result)
        return result


__all__ = ["MarketRegimeService", "regime_market", "regime_matches_market"]
