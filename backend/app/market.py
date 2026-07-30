"""Public-market-data adapter with explicit source metadata and short-lived cache."""
from __future__ import annotations

import time
import re
import os
from datetime import datetime, timedelta
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
    HK_CACHE_SECONDS = 300
    DIRECTORY_CACHE_SECONDS = 6 * 60 * 60

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, object, datetime, str]] = {}
        self._directory_cache: dict[str, tuple[float, object, datetime, str]] = {}
        self._lock = Lock()
        self._provider = os.getenv("THIRD_HAND_MARKET_PROVIDER", "akshare").lower()
        self._tushare_token = os.getenv("TUSHARE_TOKEN", "").strip()
        if self._provider not in {"akshare", "tushare", "auto"}:
            raise ValueError("THIRD_HAND_MARKET_PROVIDER must be akshare, tushare, or auto")

    def quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        normalized = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
        if not normalized:
            return []
        hk_symbols = [symbol.zfill(5) for symbol in normalized if self._is_hk(symbol)]
        a_symbols = [symbol for symbol in normalized if not self._is_hk(symbol) and len(symbol) == 6 and symbol.isdigit()]
        invalid_symbols = [symbol for symbol in normalized if symbol not in hk_symbols and symbol not in a_symbols]
        quotes: list[dict[str, object]] = []
        if hk_symbols:
            quotes.extend(self._hk_quotes(hk_symbols))
        if a_symbols:
            etf_symbols = [symbol for symbol in a_symbols if symbol.startswith(("15", "16", "51", "56", "58"))]
            stock_symbols = [symbol for symbol in a_symbols if symbol not in etf_symbols]
            if self._use_tushare():
                try:
                    quotes.extend(self._tushare_a_quotes(a_symbols))
                except MarketDataUnavailable:
                    if self._provider != "auto":
                        raise
                    quotes.extend(self._public_a_quotes(stock_symbols, etf_symbols, "Tushare 不可用时的公开源快照，不应用于交易执行。"))
            else:
                quotes.extend(self._public_a_quotes(stock_symbols, etf_symbols, "公开源快照，不应用于交易执行。"))
        returned = {str(quote["symbol"]) for quote in quotes}
        for symbol in normalized:
            if symbol not in returned:
                reason = "证券代码应为 6 位 A 股/ETF 或 5 位港股代码。" if symbol in invalid_symbols else "未找到该代码的行情；请核对证券代码或稍后重试。"
                quotes.append({"symbol": symbol, "name": symbol, "price": None, "change": None, "change_percent": None,
                    "currency": "CNY", "source": "代码校验", "retrieved_at": beijing_now(), "as_of": None,
                    "is_realtime": False, "delay_seconds": None, "license_scope": "n/a", "freshness_note": reason})
        return quotes

    def _public_a_quotes(self, stock_symbols: list[str], etf_symbols: list[str], freshness_note: str) -> list[dict[str, object]]:
        quotes = self._from_frame(self._frame("a"), stock_symbols, "CNY", freshness_note) if stock_symbols else []
        if etf_symbols:
            quotes.extend(self._from_frame(self._frame("etf"), etf_symbols, "CNY", freshness_note))
        return quotes

    def _use_tushare(self) -> bool:
        return bool(self._tushare_token) and self._provider in {"tushare", "auto"}

    def _tushare_a_quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        """Personal-research A-share end-of-day snapshots; never label as real-time."""
        try:
            import tushare as ts
        except ImportError as error:
            raise MarketDataUnavailable("未安装 Tushare，请在 backend 虚拟环境运行 pip install -r requirements.txt。", "tushare_not_installed") from error
        records: list[dict[str, object]] = []
        try:
            client = ts.pro_api(self._tushare_token)
            start_date = (beijing_now() - timedelta(days=10)).strftime("%Y%m%d")
            for symbol in symbols:
                exchange = "BJ" if symbol.startswith(("4", "8")) else ("SH" if symbol.startswith(("5", "6", "9")) else "SZ")
                is_etf = symbol.startswith(("15", "16", "51", "56", "58"))
                frame = (client.fund_daily if is_etf else client.daily)(ts_code=f"{symbol}.{exchange}", start_date=start_date)
                if frame is None or frame.empty:
                    continue
                latest = frame.iloc[0]
                close = float(latest["close"])
                pre_close = float(latest["pre_close"])
                records.append({
                    "symbol": symbol, "name": symbol, "price": close,
                    "change": round(close - pre_close, 4), "change_percent": round(float(latest["pct_chg"]), 2),
                    "open": latest.get("open"), "high": latest.get("high"), "low": latest.get("low"),
                    "previous_close": pre_close, "volume": latest.get("vol"), "amount": latest.get("amount"),
                    "currency": "CNY", "source": "Tushare Pro", "retrieved_at": beijing_now(),
                    "as_of": str(latest["trade_date"]), "is_realtime": False, "delay_seconds": None,
                    "license_scope": "personal-research-only",
                    "freshness_note": "个人研究用盘后日线快照，不是实时行情，也不得用于交易执行。",
                })
        except Exception as error:
            raise MarketDataUnavailable("Tushare 盘后行情暂时不可用，请稍后刷新。", "tushare_unavailable") from error
        return records

    def _hk_quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        """Prefer the trading-session spot snapshot and fall back to daily closes."""
        spot_note = "交易时段内的公开行情快照，可能存在延迟，不得用于交易执行。"
        try:
            spot_quotes = self._from_frame(self._frame("hk"), symbols, "HKD", spot_note)
        except MarketDataUnavailable:
            spot_quotes = []
        returned = {str(quote["symbol"]) for quote in spot_quotes}
        missing = [symbol for symbol in symbols if symbol not in returned]
        if not missing:
            return spot_quotes

        try:
            import akshare as ak
        except ImportError as error:
            raise MarketDataUnavailable("未安装 AKShare，请在 backend 虚拟环境运行 pip install -r requirements.txt。", "akshare_not_installed") from error

        quotes = list(spot_quotes)
        for symbol in missing:
            try:
                data = ak.stock_hk_daily(symbol=symbol)
                latest = data.iloc[-1]
                previous = data.iloc[-2] if len(data.index) > 1 else None
                price = float(latest["close"])
                previous_close = float(previous["close"]) if previous is not None else None
                change_percent = None if not previous_close else round((price - previous_close) / previous_close * 100, 2)
                quotes.append({
                    "symbol": symbol, "name": symbol, "price": price, "change": None,
                    "change_percent": change_percent, "open": latest.get("open"), "high": latest.get("high"),
                    "low": latest.get("low"), "previous_close": previous_close, "volume": latest.get("volume"),
                    "amount": latest.get("amount"), "currency": "HKD", "source": "新浪财经 / AKShare",
                    "retrieved_at": beijing_now(), "as_of": str(latest.name), "is_realtime": False,
                    "delay_seconds": None, "license_scope": "public-source-review-required",
                    "freshness_note": "实时快照暂不可用，当前为最近交易日收盘数据。",
                })
            except Exception as error:
                raise MarketDataUnavailable("港股行情源暂时不可用，请稍后刷新。") from error
        return quotes

    def lookup_symbols(self, names: list[str]) -> list[dict[str, object]]:
        """Find A-share and Hong Kong listings by a user-provided security name."""
        requested = list(dict.fromkeys(name.strip() for name in names if name.strip()))
        if not requested:
            return []
        matches = {name: [] for name in requested}
        for market, currency in (("a", "CNY"), ("etf", "CNY"), ("hk", "HKD")):
            for record in self._lookup_from_frame(self._directory_frame(market), requested, market, currency):
                matches[record.pop("query")].append(record)
        return [{"query": name, "matches": matches[name]} for name in requested]

    @staticmethod
    def _is_hk(symbol: str) -> bool:
        # A five-digit code (including leading zero) is treated as a Hong Kong listing.
        return len(symbol) == 5 and symbol.isdigit()

    def _frame(self, market: str):
        with self._lock:
            cached = self._cache.get(market)
            cache_seconds = self.HK_CACHE_SECONDS if market == "hk" else self.CACHE_SECONDS
            if cached and time.monotonic() - cached[0] < cache_seconds:
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
            elif market == "etf":
                frame = ak.fund_etf_spot_em()
                source = "东方财富 / AKShare"
            else:
                frame = ak.stock_zh_a_spot_em()
                source = "东方财富 / AKShare"
        except Exception as error:
            raise MarketDataUnavailable("公开行情源暂时不可用，请稍后刷新。") from error
        retrieved_at = beijing_now()
        with self._lock:
            self._cache[market] = (time.monotonic(), frame, retrieved_at, source)
        return frame, retrieved_at, source

    def _directory_frame(self, market: str):
        """Return a long-lived listing directory; names and codes change far less often than prices."""
        with self._lock:
            cached = self._directory_cache.get(market)
            if cached and time.monotonic() - cached[0] < self.DIRECTORY_CACHE_SECONDS:
                return cached[1], cached[2], cached[3]
        frame, retrieved_at, source = self._frame(market)
        with self._lock:
            self._directory_cache[market] = (time.monotonic(), frame, retrieved_at, source)
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
            "as_of": retrieved_at.date().isoformat(), "is_realtime": False, "delay_seconds": None,
            "license_scope": "public-source-review-required",
        } for record in records]

    @staticmethod
    def _lookup_from_frame(frame_and_time, names: list[str], market: str, currency: str) -> list[dict[str, str]]:
        frame, _, _ = frame_and_time
        try:
            data = frame.copy()
            code_column = "代码"
            name_column = "名称" if "名称" in data.columns else "中文名称"
            width = 5 if market == "hk" else 6
            data[code_column] = data[code_column].astype(str).str.zfill(width)
        except (AttributeError, KeyError) as error:
            raise MarketDataUnavailable("行情源字段已变更，等待适配更新。") from error

        results: list[dict[str, str]] = []
        for query in names:
            normalized_query = MarketDataService._normalize_name(query)
            if not normalized_query:
                continue
            exact = data[data[name_column].astype(str).map(MarketDataService._normalize_name) == normalized_query]
            candidates = exact
            match_type = "exact"
            if candidates.empty:
                candidates = data[data[name_column].astype(str).map(
                    lambda value: normalized_query in MarketDataService._normalize_name(value)
                )]
                match_type = "partial"
            for _, row in candidates.head(10).iterrows():
                results.append({
                    "query": query,
                    "symbol": str(row[code_column]),
                    "name": str(row[name_column]),
                    "market": "HK" if market == "hk" else ("ETF" if market == "etf" else "CN"),
                    "currency": currency,
                    "match_type": match_type,
                })
        return results

    @staticmethod
    def _normalize_name(value: object) -> str:
        return re.sub(r"[\s\-_.·・()（）]", "", str(value)).upper()
