"""Optional, bounded HiThink Financial API integration for A-share data.

The integration is deliberately opt-in.  When disabled or unconfigured the
existing AKShare/Tencent/Tushare provider behavior is untouched.  When enabled,
HiThink is attempted only for explicit A-share symbol/name lookup, explicit
quote batches, and single-symbol daily history.  Any provider failure degrades
to the pre-existing provider chain.
"""
from __future__ import annotations

from datetime import datetime
import logging
import os
import time
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.decimal_utils import decimal_text
from app.market import MarketDataService
from app.price_history import PriceHistoryService
from app.time_utils import beijing_now


logger = logging.getLogger(__name__)
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
SOURCE_NAME = "HiThink Financial API"
HISTORY_SOURCE_NAME = "HiThink Financial API daily history"
_RETRYABLE_CODES = {4001, 5001, 5002, 5003}
_MAX_ATTEMPTS = 3
_INSTALLED = False

# Import ordering matters.  bootstrap.runtime imports this module only after the
# existing daily-history policy/compatibility installers run, so the captured
# history callable already contains those governance layers and remains the
# fallback path.
_ORIGINAL_MARKET_QUOTES = MarketDataService.quotes
_ORIGINAL_MARKET_LOOKUP = MarketDataService.lookup_symbols
_ORIGINAL_HISTORY_REFRESH_RANGE = PriceHistoryService._refresh_range


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class HiThinkFinanceError(RuntimeError):
    """A bounded provider failure safe to expose only as provider metadata."""

    def __init__(
        self,
        message: str,
        *,
        code: int | str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id


class HiThinkFinanceClient:
    """Small REST client for the three capabilities used by the PoC."""

    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str,
        base_url: str = "https://fuyao.aicubes.cn",
        timeout_seconds: float = 5.0,
        max_batch: int = 20,
    ) -> None:
        self.enabled = bool(enabled)
        self.api_key = str(api_key or "").strip()
        self.base_url = str(base_url or "https://fuyao.aicubes.cn").rstrip("/")
        self.timeout_seconds = max(0.5, float(timeout_seconds))
        self.max_batch = min(50, max(1, int(max_batch)))
        self._resolution_cache: dict[str, dict[str, object]] = {}

    @classmethod
    def from_env(cls) -> "HiThinkFinanceClient":
        timeout_raw = os.getenv("HITHINK_FINANCE_TIMEOUT_SECONDS", "5").strip()
        batch_raw = os.getenv("HITHINK_FINANCE_MAX_BATCH", "20").strip()
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = 5.0
        try:
            max_batch = int(batch_raw)
        except ValueError:
            max_batch = 20
        return cls(
            enabled=_env_enabled("HITHINK_FINANCE_ENABLED", False),
            api_key=os.getenv("HITHINK_FINANCE_API_KEY", ""),
            base_url=os.getenv("HITHINK_FINANCE_BASE_URL", "https://fuyao.aicubes.cn"),
            timeout_seconds=timeout_seconds,
            max_batch=max_batch,
        )

    @property
    def available(self) -> bool:
        return self.enabled and bool(self.api_key)

    def _request(
        self,
        path: str,
        params: dict[str, object],
    ) -> tuple[dict[str, object], str | None]:
        if not self.available:
            raise HiThinkFinanceError("HiThink provider is disabled or API key is missing")

        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = httpx.get(
                    url,
                    params=params,
                    headers={"X-api-key": self.api_key},
                    timeout=self.timeout_seconds,
                )
            except httpx.RequestError as error:
                last_error = error
                if attempt + 1 < _MAX_ATTEMPTS:
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise HiThinkFinanceError("HiThink transport request failed") from error

            status_code = int(response.status_code)
            if status_code != 200:
                if (status_code == 429 or status_code >= 500) and attempt + 1 < _MAX_ATTEMPTS:
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise HiThinkFinanceError(
                    f"HiThink returned HTTP {status_code}",
                    code=status_code,
                )

            try:
                payload = response.json()
            except ValueError as error:
                raise HiThinkFinanceError("HiThink returned invalid JSON") from error
            if not isinstance(payload, dict):
                raise HiThinkFinanceError("HiThink returned an invalid response envelope")

            request_id = str(payload.get("request_id") or "").strip() or None
            raw_code = payload.get("code", -1)
            try:
                code = int(raw_code)
            except (TypeError, ValueError):
                code = -1
            if code == 0:
                data = payload.get("data")
                return (data if isinstance(data, dict) else {}), request_id

            message = str(payload.get("message") or "HiThink provider request failed")
            if code in _RETRYABLE_CODES and attempt + 1 < _MAX_ATTEMPTS:
                time.sleep(0.25 * (2**attempt))
                continue
            raise HiThinkFinanceError(message, code=code, request_id=request_id)

        raise HiThinkFinanceError("HiThink request failed after bounded retries") from last_error

    def search(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        cleaned = str(query or "").strip()
        if not cleaned:
            return []
        data, _ = self._request(
            "/api/meta/tickers/search",
            {
                "q": cleaned,
                "asset_type": "a-share",
                "limit": min(5, max(1, int(limit))),
            },
        )
        items = data.get("item")
        if not isinstance(items, list):
            return []
        results: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("asset_type") or "") != "a-share":
                continue
            ticker = str(item.get("ticker") or "").strip().upper()
            thscode = str(item.get("thscode") or "").strip().upper()
            if not ticker or not thscode:
                continue
            results.append({
                "ticker": ticker,
                "thscode": thscode,
                "name": str(item.get("name") or ticker).strip(),
                "exchange": str(item.get("exchange") or "").strip().upper(),
                "asset_type": "a-share",
                "currency": str(item.get("currency") or "CNY").strip().upper() or "CNY",
            })
        return results[:5]

    def _resolve(self, query: str) -> dict[str, object]:
        cleaned = str(query or "").strip()
        cache_key = cleaned.upper()
        cached = self._resolution_cache.get(cache_key)
        if cached is not None:
            return dict(cached)

        items = self.search(cleaned, limit=5)
        if not items:
            raise HiThinkFinanceError("HiThink did not resolve the requested A-share", code="symbol_not_found")

        upper = cleaned.upper()
        exact = [
            item for item in items
            if str(item.get("ticker") or "").upper() == upper
            or str(item.get("thscode") or "").upper() == upper
            or str(item.get("name") or "").strip() == cleaned
        ]
        if len(exact) == 1:
            resolved = exact[0]
        elif len(items) == 1:
            resolved = items[0]
        else:
            raise HiThinkFinanceError(
                "HiThink symbol lookup remained ambiguous; fallback required",
                code="ambiguous_symbol",
            )
        self._resolution_cache[cache_key] = dict(resolved)
        return dict(resolved)

    def quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        requested = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
        if not requested:
            return []
        resolved = [self._resolve(symbol) for symbol in requested]
        by_thscode = {str(item["thscode"]): item for item in resolved}
        quotes: list[dict[str, object]] = []

        thscodes = list(by_thscode)
        for offset in range(0, len(thscodes), self.max_batch):
            batch = thscodes[offset:offset + self.max_batch]
            # Explicit thscodes is mandatory here.  Omitting it changes the
            # official API into all-market pagination, which this PoC forbids.
            data, _request_id = self._request(
                "/api/a-share/prices/snapshot",
                {"thscodes": ",".join(batch)},
            )
            items = data.get("item")
            if not isinstance(items, list):
                continue
            for row in items:
                if not isinstance(row, dict):
                    continue
                thscode = str(row.get("thscode") or "").strip().upper()
                metadata = by_thscode.get(thscode)
                if metadata is None:
                    continue
                ticker = str(metadata["ticker"])
                quotes.append({
                    "symbol": ticker,
                    "name": str(metadata.get("name") or ticker),
                    "price": row.get("last_price"),
                    "change": row.get("price_change"),
                    "change_percent": row.get("price_change_ratio_pct"),
                    "open": row.get("open_price"),
                    "high": row.get("high_price"),
                    "low": row.get("low_price"),
                    "previous_close": row.get("prev_price"),
                    "volume": row.get("volume"),
                    "amount": row.get("turnover"),
                    "currency": str(metadata.get("currency") or "CNY"),
                    "source": SOURCE_NAME,
                    "retrieved_at": beijing_now(),
                    "as_of": None,
                    "is_realtime": False,
                    "delay_seconds": None,
                    "license_scope": "HiThink-account-capability",
                    "freshness_note": "同花顺官方最新行情快照；显式标的模式不返回统一行情时间。",
                })
        return quotes

    @staticmethod
    def _date_ms(value: str) -> int:
        parsed = datetime.strptime(value, "%Y%m%d").replace(tzinfo=SHANGHAI_TIMEZONE)
        return int(parsed.timestamp() * 1000)

    def historical(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> tuple[list[dict[str, object]], str | None]:
        metadata = self._resolve(symbol)
        data, request_id = self._request(
            "/api/a-share/prices/historical",
            {
                "thscode": str(metadata["thscode"]),
                "interval": "1d",
                "start": self._date_ms(start),
                "end": self._date_ms(end),
                "adjust": "forward",
            },
        )
        items = data.get("item")
        if not isinstance(items, list):
            return [], request_id

        bars: list[dict[str, object]] = []
        for row in items:
            if not isinstance(row, dict):
                continue
            try:
                date_ms = int(row.get("date_ms"))
                trading_date = datetime.fromtimestamp(
                    date_ms / 1000,
                    tz=SHANGHAI_TIMEZONE,
                ).date().isoformat()
            except (TypeError, ValueError, OSError, OverflowError):
                continue
            close = decimal_text(row.get("close_price"))
            if close is None:
                continue
            bars.append({
                "trading_date": trading_date,
                "open": decimal_text(row.get("open_price")),
                "close": close,
                "high": decimal_text(row.get("high_price")),
                "low": decimal_text(row.get("low_price")),
                "volume": decimal_text(row.get("volume")),
                "amount": decimal_text(row.get("turnover")),
                "adjustment": "qfq",
                "source": HISTORY_SOURCE_NAME,
            })
        return bars, request_id


def _client_for(service: object) -> HiThinkFinanceClient:
    client = getattr(service, "_hithink_finance_client", None)
    if isinstance(client, HiThinkFinanceClient):
        return client
    client = HiThinkFinanceClient.from_env()
    setattr(service, "_hithink_finance_client", client)
    return client


def _candidate_a_share(symbol: str) -> bool:
    return (
        len(symbol) == 6
        and symbol.isdigit()
        and not symbol.startswith(("15", "16", "51", "56", "58"))
    )


def _quotes_with_hithink(
    self: MarketDataService,
    symbols: list[str],
    force_refresh: bool = False,
) -> list[dict[str, object]]:
    client = _client_for(self)
    if not client.available:
        return _ORIGINAL_MARKET_QUOTES(self, symbols, force_refresh=force_refresh)

    normalized = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    candidates = [symbol for symbol in normalized if _candidate_a_share(symbol)]
    if not candidates:
        return _ORIGINAL_MARKET_QUOTES(self, symbols, force_refresh=force_refresh)

    try:
        preferred = client.quotes(candidates)
    except HiThinkFinanceError as error:
        logger.warning(
            "HiThink quote fallback code=%s request_id=%s error_type=%s",
            error.code,
            error.request_id,
            type(error).__name__,
        )
        return _ORIGINAL_MARKET_QUOTES(self, symbols, force_refresh=force_refresh)
    except Exception as error:
        logger.warning("HiThink quote fallback error_type=%s", type(error).__name__)
        return _ORIGINAL_MARKET_QUOTES(self, symbols, force_refresh=force_refresh)

    by_symbol = {str(item.get("symbol") or "").upper(): item for item in preferred}
    missing = [symbol for symbol in normalized if symbol not in by_symbol]
    if missing:
        fallback = _ORIGINAL_MARKET_QUOTES(self, missing, force_refresh=force_refresh)
        by_symbol.update({str(item.get("symbol") or "").upper(): item for item in fallback})

    if len(normalized) == 1 and normalized[0] in by_symbol and _candidate_a_share(normalized[0]):
        try:
            by_symbol[normalized[0]].update(self._a_order_book(normalized[0]))
        except Exception as error:
            logger.warning(
                "A-share order book unavailable after HiThink quote symbol=%s error_type=%s",
                normalized[0],
                type(error).__name__,
            )
    return [by_symbol[symbol] for symbol in normalized if symbol in by_symbol]


def _lookup_with_hithink(
    self: MarketDataService,
    names: list[str],
) -> list[dict[str, object]]:
    client = _client_for(self)
    if not client.available:
        return _ORIGINAL_MARKET_LOOKUP(self, names)

    requested = list(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    if not requested:
        return []
    results: list[dict[str, object]] = []
    for query in requested:
        try:
            items = client.search(query, limit=5)
        except HiThinkFinanceError as error:
            logger.warning(
                "HiThink symbol lookup fallback code=%s request_id=%s error_type=%s",
                error.code,
                error.request_id,
                type(error).__name__,
            )
            fallback = _ORIGINAL_MARKET_LOOKUP(self, [query])
            results.extend(fallback)
            continue
        except Exception as error:
            logger.warning("HiThink symbol lookup fallback error_type=%s", type(error).__name__)
            results.extend(_ORIGINAL_MARKET_LOOKUP(self, [query]))
            continue

        if not items:
            results.extend(_ORIGINAL_MARKET_LOOKUP(self, [query]))
            continue
        matches = [{
            "symbol": str(item["ticker"]),
            "name": str(item.get("name") or item["ticker"]),
            "market": "CN",
            "currency": str(item.get("currency") or "CNY"),
            "source": SOURCE_NAME,
        } for item in items]
        results.append({
            "query": query,
            "matches": matches,
            "lookup_status": "matched",
            "lookup_message": f"HiThink 官方 A 股目录返回 {len(matches)} 个候选代码。",
        })
    return results


def _history_with_hithink(
    self: PriceHistoryService,
    store: Any,
    symbol: str,
    start: str,
    end: str,
    trigger: str | None = None,
    run_id: str | None = None,
) -> int:
    symbol = str(symbol or "").strip().upper()
    client = _client_for(self)
    if not client.available or self._kind(symbol) != "a":
        return _ORIGINAL_HISTORY_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )

    started_at = beijing_now().isoformat()
    started = time.monotonic()
    if self._circuit_open(store, "hithink"):
        self._record_attempt(
            store,
            symbol=symbol,
            provider="hithink",
            status="skipped",
            started_at=started_at,
            elapsed_ms=0,
            run_id=run_id,
            trigger=trigger,
            detail={"reason": "circuit_open"},
        )
        return _ORIGINAL_HISTORY_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )

    try:
        bars, request_id = client.historical(symbol, start, end)
    except HiThinkFinanceError as error:
        self._record_attempt(
            store,
            symbol=symbol,
            provider="hithink",
            status="error",
            started_at=started_at,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            run_id=run_id,
            trigger=trigger,
            error_type=type(error).__name__,
            error_message=str(error),
            detail={"code": error.code, "request_id": error.request_id},
        )
        logger.warning(
            "HiThink history fallback symbol=%s code=%s request_id=%s",
            symbol,
            error.code,
            error.request_id,
        )
        return _ORIGINAL_HISTORY_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )
    except Exception as error:
        self._record_attempt(
            store,
            symbol=symbol,
            provider="hithink",
            status="error",
            started_at=started_at,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            run_id=run_id,
            trigger=trigger,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        logger.warning("HiThink history fallback symbol=%s error_type=%s", symbol, type(error).__name__)
        return _ORIGINAL_HISTORY_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )

    if not bars:
        self._record_attempt(
            store,
            symbol=symbol,
            provider="hithink",
            status="empty",
            started_at=started_at,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            run_id=run_id,
            trigger=trigger,
            detail={"request_id": request_id},
        )
        return _ORIGINAL_HISTORY_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )

    # Preserve the existing completed-session closing-bar repair before writing.
    self._append_sina_closing_bar(
        symbol,
        bars,
        store=store,
        trigger=trigger,
        run_id=run_id,
    )
    store.save_daily_prices(symbol, bars)
    elapsed_ms = round((time.monotonic() - started) * 1000)
    self._record_attempt(
        store,
        symbol=symbol,
        provider="hithink",
        status="ok",
        started_at=started_at,
        elapsed_ms=elapsed_ms,
        run_id=run_id,
        trigger=trigger,
        bar_count=len(bars),
        detail={"request_id": request_id},
    )
    self._record_attempt(
        store,
        symbol=symbol,
        provider="overall",
        status="ok",
        started_at=started_at,
        elapsed_ms=elapsed_ms,
        run_id=run_id,
        trigger=trigger,
        bar_count=len(bars),
        detail={"provider": "hithink", "request_id": request_id},
    )
    return len(bars)


def install() -> None:
    """Install the optional provider as an outer, fail-open acquisition layer."""
    global _INSTALLED
    if _INSTALLED:
        return
    MarketDataService.quotes = _quotes_with_hithink
    MarketDataService.lookup_symbols = _lookup_with_hithink
    PriceHistoryService._refresh_range = _history_with_hithink
    _INSTALLED = True
