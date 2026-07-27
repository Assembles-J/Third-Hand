"""Public-market-data adapter with explicit source metadata and short-lived cache."""
from __future__ import annotations

import time
from datetime import datetime
from threading import Lock

from app.time_utils import beijing_now


class MarketDataUnavailable(RuntimeError):
    """The public upstream was unavailable or returned an unexpected payload."""

    def __init__(self, message: str, code: str = "upstream_unavailable") -> None:
        super().__init__(message)
        self.code = code


class MarketDataService:
    # A cache protects public endpoints from a request per app screen refresh.
    CACHE_SECONDS = 60

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, object, datetime, str]] = {}
        self._lock = Lock()

    def quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        normalized = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
        if not normalized:
            return []
        hk_symbols = [symbol.zfill(5) for symbol in normalized if self._is_hk(symbol)]
        a_symbols = [symbol for symbol in normalized if not self._is_hk(symbol)]
        quotes: list[dict[str, object]] = []
        if hk_symbols:
            quotes.extend(self._from_frame(self._frame("hk"), hk_symbols, "HKD", "公开源快照，港股行情存在约 15 分钟延时。"))
        if a_symbols:
            quotes.extend(self._from_frame(self._frame("a"), a_symbols, "CNY", "公开源快照，不应用于交易执行。"))
        return quotes

    @staticmethod
    def _is_hk(symbol: str) -> bool:
        # A five-digit code (including leading zero) is treated as a Hong Kong listing.
        return len(symbol) == 5 and symbol.isdigit()

    def _frame(self, market: str):
        with self._lock:
            cached = self._cache.get(market)
            if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
                return cached[1], cached[2], cached[3]
        try:
            import akshare as ak
        except ImportError as error:
            raise MarketDataUnavailable(
                "未安装 AKShare：请在 backend 虚拟环境运行 pip install -r requirements.txt。",
                "akshare_not_installed",
            ) from error
        try:
            if market == "hk":
                try:
                    frame = ak.stock_hk_spot_em()
                    source = "东方财富 / AKShare"
                except Exception:
                    # The Eastmoney endpoint is paginated and may close connections.
                    frame = ak.stock_hk_spot()
                    source = "新浪财经 / AKShare"
            else:
                frame = ak.stock_zh_a_spot_em()
                source = "东方财富 / AKShare"
        except Exception as error:
            raise MarketDataUnavailable("公开行情源暂时不可用，请稍后刷新。") from error
        retrieved_at = beijing_now()
        with self._lock:
            self._cache[market] = (time.monotonic(), frame, retrieved_at, source)
        return frame, retrieved_at, source

    @staticmethod
    def _from_frame(frame_and_time, symbols: list[str], currency: str, freshness_note: str) -> list[dict[str, object]]:
        frame, retrieved_at, source = frame_and_time
        try:
            data = frame.copy()
            data["代码"] = data["代码"].astype(str).str.zfill(5 if currency == "HKD" else 6)
            records = data[data["代码"].isin(symbols)].to_dict("records")
        except (AttributeError, KeyError) as error:
            raise MarketDataUnavailable("行情源字段已变更，等待适配更新。") from error
        return [{
            "symbol": record["代码"], "name": record.get("名称", record.get("中文名称", "")), "price": record.get("最新价"),
            "change": record.get("涨跌额"), "change_percent": record.get("涨跌幅"), "open": record.get("今开"),
            "high": record.get("最高"), "low": record.get("最低"), "previous_close": record.get("昨收"),
            "volume": record.get("成交量"), "amount": record.get("成交额"), "currency": currency,
            "source": source, "retrieved_at": retrieved_at, "freshness_note": freshness_note,
        } for record in records]
