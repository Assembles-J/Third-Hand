"""Production daily-history policy: local-first, qfq-only, provider-aware.

This module is installed before ``app.application`` is imported.  It keeps the
existing PriceHistoryService/PortfolioStore public API intact while tightening
the formal daily-price contract:

* formal cache rows use ISO ``YYYY-MM-DD`` dates and ``adjustment=qfq``;
* legacy/provider-default rows are quarantined once instead of silently reused;
* ordinary A-share remote fallback prefers Tencent, then Tushare qfq, then
  Eastmoney; Sina remains a post-close one-bar supplement;
* provider calls are serialized with conservative, configurable minimum gaps.

Dynamic/research data discovery remains outside this module and therefore cannot
bypass the existing POLICY / RESEARCH_ONLY governance boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import os
from threading import Lock
import time
from typing import Iterable

from app.decimal_utils import decimal_text
from app import price_history as _price_history
from app import storage as _storage

logger = logging.getLogger(__name__)

MIGRATION_ID = "0015_daily_price_qfq_contract"
_INSTALLED = False

_ORIGINAL_STORE_INIT = _storage.PortfolioStore.__init__
_ORIGINAL_SAVE_DAILY_PRICES = _storage.PortfolioStore.save_daily_prices
_ORIGINAL_REPLACE_DAILY_PRICES = _storage.PortfolioStore.replace_daily_prices
_ORIGINAL_REFRESH_RANGE = _price_history.PriceHistoryService._refresh_range
_ORIGINAL_TENCENT_BARS = _price_history.PriceHistoryService._tencent_bars
_ORIGINAL_SINA_CLOSING = _price_history.PriceHistoryService._append_sina_closing_bar


class _RateLimiter:
    def __init__(self, env_name: str, default_seconds: float) -> None:
        self.env_name = env_name
        self.default_seconds = default_seconds
        self._lock = Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        try:
            gap = max(0.0, float(os.getenv(self.env_name, str(self.default_seconds))))
        except ValueError:
            gap = self.default_seconds
        with self._lock:
            now = time.monotonic()
            remaining = gap - (now - self._last_call)
            if remaining > 0:
                time.sleep(remaining)
            self._last_call = time.monotonic()


_LIMITERS = {
    "tencent": _RateLimiter("HISTORY_TENCENT_MIN_INTERVAL_SECONDS", 0.5),
    "tushare": _RateLimiter("HISTORY_TUSHARE_MIN_INTERVAL_SECONDS", 0.5),
    "sina_minute": _RateLimiter("HISTORY_SINA_MIN_INTERVAL_SECONDS", 2.0),
    "akshare": _RateLimiter("HISTORY_EASTMONEY_MIN_INTERVAL_SECONDS", 2.0),
}


def _iso_date(value: object) -> str:
    raw = str(value).strip()
    if len(raw) == 8 and raw.isdigit():
        raw = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return date.fromisoformat(raw[:10]).isoformat()


def _validated_qfq_rows(bars: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for bar in bars:
        item = dict(bar)
        item["trading_date"] = _iso_date(item["trading_date"])
        if str(item.get("adjustment", "qfq")).lower() != "qfq":
            raise ValueError("formal daily_price_cache accepts qfq bars only")
        item["adjustment"] = "qfq"
        rows.append(item)
    return rows


def _migrate_daily_price_cache(store: _storage.PortfolioStore) -> None:
    """Quarantine incompatible legacy bars and normalize safe qfq date keys once."""
    with store._connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        if connection.execute(
            "SELECT 1 FROM schema_migrations WHERE migration_id=?", (MIGRATION_ID,)
        ).fetchone():
            return
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_price_quarantine (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
              open TEXT, close REAL NOT NULL, high REAL, low REAL,
              volume TEXT, amount TEXT, amplitude_percent TEXT,
              change_percent TEXT, change_amount TEXT, turnover_rate TEXT,
              adjustment TEXT NOT NULL, source TEXT NOT NULL, updated_at TEXT NOT NULL,
              quarantine_reason TEXT NOT NULL, quarantined_at TEXT NOT NULL
            )
        """)
        dirty_where = (
            "adjustment <> 'qfq' OR length(trading_date) <> 10 "
            "OR substr(trading_date,5,1) <> '-' OR substr(trading_date,8,1) <> '-'"
        )
        impacted = [
            str(row[0])
            for row in connection.execute(
                f"SELECT DISTINCT symbol FROM daily_price_cache WHERE {dirty_where}"
            ).fetchall()
        ]
        now = datetime.now(timezone.utc).isoformat()
        connection.execute(f"""
            INSERT INTO daily_price_quarantine (
              symbol,trading_date,open,close,high,low,volume,amount,
              amplitude_percent,change_percent,change_amount,turnover_rate,
              adjustment,source,updated_at,quarantine_reason,quarantined_at
            )
            SELECT symbol,trading_date,open,close,high,low,volume,amount,
                   amplitude_percent,change_percent,change_amount,turnover_rate,
                   adjustment,source,updated_at,
                   CASE WHEN adjustment <> 'qfq' THEN 'non_qfq'
                        ELSE 'non_iso_date' END,
                   ?
            FROM daily_price_cache WHERE {dirty_where}
        """, (now,))

        # Non-qfq rows must never feed formal policy/risk calculations. They are
        # retained in the quarantine table for audit and can be rebuilt remotely.
        connection.execute("DELETE FROM daily_price_cache WHERE adjustment <> 'qfq'")

        # Resolve qfq rows that differ only by compact-vs-ISO date key.  Prefer
        # the already-ISO row when both exist, otherwise normalize in place.
        connection.execute("""
            DELETE FROM daily_price_cache AS compact
            WHERE length(compact.trading_date)=8
              AND compact.trading_date NOT LIKE '%-%'
              AND EXISTS (
                SELECT 1 FROM daily_price_cache AS iso
                WHERE iso.symbol=compact.symbol
                  AND iso.trading_date=substr(compact.trading_date,1,4)||'-'||
                                      substr(compact.trading_date,5,2)||'-'||
                                      substr(compact.trading_date,7,2)
              )
        """)
        connection.execute("""
            UPDATE daily_price_cache
            SET trading_date=substr(trading_date,1,4)||'-'||substr(trading_date,5,2)||'-'||substr(trading_date,7,2)
            WHERE adjustment='qfq' AND length(trading_date)=8 AND trading_date NOT LIKE '%-%'
        """)

        if impacted:
            marks = ",".join("?" for _ in impacted)
            connection.execute(f"DELETE FROM risk_cache WHERE symbol IN ({marks})", impacted)
        # These caches aggregate or materialize derived data and are cheap to
        # rebuild compared with carrying a mixed-adjustment history forward.
        connection.execute("DELETE FROM portfolio_analysis_cache")
        connection.execute("DELETE FROM feature_values")
        connection.execute(
            "INSERT INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)",
            (MIGRATION_ID, now),
        )
        logger.warning(
            "daily-price contract migration applied migration=%s impacted_symbols=%s",
            MIGRATION_ID,
            len(impacted),
        )


def _store_init(self, *args, **kwargs) -> None:
    _ORIGINAL_STORE_INIT(self, *args, **kwargs)
    _migrate_daily_price_cache(self)


def _save_daily_prices(self, symbol: str, bars: list[dict[str, object]]) -> None:
    _ORIGINAL_SAVE_DAILY_PRICES(self, symbol, _validated_qfq_rows(bars))


def _replace_daily_prices(self, symbol: str, bars: list[dict[str, object]]) -> None:
    _ORIGINAL_REPLACE_DAILY_PRICES(self, symbol, _validated_qfq_rows(bars))


def _tencent_bars(self, *args, **kwargs):
    _LIMITERS["tencent"].wait()
    return _ORIGINAL_TENCENT_BARS(self, *args, **kwargs)


def _sina_closing_bar(self, *args, **kwargs):
    _LIMITERS["sina_minute"].wait()
    return _ORIGINAL_SINA_CLOSING(self, *args, **kwargs)


def _tushare_bars_qfq(self, store, symbol: str, start: str, end: str, trigger=None, run_id=None):
    """Fetch A-share Tushare history through pro_bar with explicit qfq output."""
    started_at = _price_history.beijing_now().isoformat()
    started = time.monotonic()
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        self._record_attempt(
            store, symbol=symbol, provider="tushare", status="skipped",
            started_at=started_at, elapsed_ms=0, run_id=run_id, trigger=trigger,
            detail={"reason": "tushare_token_missing"},
        )
        return []
    if self._kind(symbol) != "a" or len(symbol) == 5:
        self._record_attempt(
            store, symbol=symbol, provider="tushare", status="skipped",
            started_at=started_at, elapsed_ms=0, run_id=run_id, trigger=trigger,
            detail={"reason": "qfq_contract_not_applicable"},
        )
        return []
    if self._circuit_open(store, "tushare"):
        self._record_attempt(
            store, symbol=symbol, provider="tushare", status="skipped",
            started_at=started_at, elapsed_ms=0, run_id=run_id, trigger=trigger,
            detail={"reason": "circuit_open"},
        )
        return []
    _LIMITERS["tushare"].wait()
    try:
        import tushare as ts

        exchange = "BJ" if self._is_beijing_symbol(symbol) else ("SH" if symbol.startswith(("5", "6", "9")) else "SZ")
        ts.set_token(token)
        frame = ts.pro_bar(
            ts_code=f"{symbol}.{exchange}",
            start_date=start,
            end_date=end,
            asset="E",
            freq="D",
            adj="qfq",
        )
        if frame is None or frame.empty:
            raise ValueError("empty_response")
        bars: list[dict[str, object]] = []
        for _, row in frame.iterrows():
            trading_date = self._trading_date(row.get("trade_date"))
            close = decimal_text(row.get("close"))
            if trading_date is None or close is None:
                continue
            volume = decimal_text(float(row.get("vol")) * 100) if decimal_text(row.get("vol")) is not None else None
            amount = decimal_text(float(row.get("amount")) * 1000) if decimal_text(row.get("amount")) is not None else None
            bars.append({
                "trading_date": trading_date,
                "open": decimal_text(row.get("open")),
                "close": close,
                "high": decimal_text(row.get("high")),
                "low": decimal_text(row.get("low")),
                "volume": volume,
                "amount": amount,
                "change_percent": decimal_text(row.get("pct_chg")),
                "change_amount": decimal_text(row.get("change")),
                "adjustment": "qfq",
                "source": "Tushare pro_bar qfq",
            })
        status = "ok" if bars else "empty"
        self._record_attempt(
            store, symbol=symbol, provider="tushare", status=status,
            started_at=started_at, elapsed_ms=round((time.monotonic() - started) * 1000),
            run_id=run_id, trigger=trigger, bar_count=len(bars),
            error_type=None if bars else "ValueError",
            error_message=None if bars else "no_usable_close",
            detail={"adjustment": "qfq", "interface": "pro_bar"},
        )
        return bars
    except Exception as error:
        self._record_attempt(
            store, symbol=symbol, provider="tushare", status="error",
            started_at=started_at, elapsed_ms=round((time.monotonic() - started) * 1000),
            run_id=run_id, trigger=trigger, error_type=type(error).__name__, error_message=str(error),
            detail={"adjustment": "qfq", "interface": "pro_bar"},
        )
        logger.warning(
            "历史日线获取失败 provider=tushare_qfq symbol=%s error_type=%s elapsed_ms=%s",
            symbol, type(error).__name__, round((time.monotonic() - started) * 1000),
        )
        return []


def _eastmoney_a_bars(self, store, symbol: str, start: str, end: str, trigger=None, run_id=None):
    started_at = _price_history.beijing_now().isoformat()
    started = time.monotonic()
    if self._circuit_open(store, "akshare"):
        self._record_attempt(
            store, symbol=symbol, provider="akshare", status="skipped",
            started_at=started_at, elapsed_ms=0, run_id=run_id, trigger=trigger,
            detail={"reason": "circuit_open", "role": "last_resort"},
        )
        return []
    _LIMITERS["akshare"].wait()
    try:
        import akshare as ak
        frame = ak.stock_zh_a_hist(
            symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq"
        )
        if frame is None or frame.empty:
            raise ValueError("empty_response")
        bars: list[dict[str, object]] = []
        for _, row in frame.iterrows():
            trading_date = self._trading_date(row.get("日期"))
            close = decimal_text(row.get("收盘"))
            if trading_date is None or close is None:
                continue
            # Eastmoney volume is documented in lots; formal cache uses shares.
            volume = decimal_text(float(row.get("成交量")) * 100) if decimal_text(row.get("成交量")) is not None else None
            bars.append({
                "trading_date": trading_date,
                "open": decimal_text(row.get("开盘")),
                "close": close,
                "high": decimal_text(row.get("最高")),
                "low": decimal_text(row.get("最低")),
                "volume": volume,
                "amount": decimal_text(row.get("成交额")),
                "amplitude_percent": decimal_text(row.get("振幅")),
                "change_percent": decimal_text(row.get("涨跌幅")),
                "change_amount": decimal_text(row.get("涨跌额")),
                "turnover_rate": decimal_text(row.get("换手率")),
                "adjustment": "qfq",
                "source": "AKShare Eastmoney qfq",
            })
        self._record_attempt(
            store, symbol=symbol, provider="akshare", status="ok" if bars else "empty",
            started_at=started_at, elapsed_ms=round((time.monotonic() - started) * 1000),
            run_id=run_id, trigger=trigger, bar_count=len(bars),
            detail={"role": "last_resort", "adjustment": "qfq"},
        )
        return bars
    except Exception as error:
        self._record_attempt(
            store, symbol=symbol, provider="akshare", status="error",
            started_at=started_at, elapsed_ms=round((time.monotonic() - started) * 1000),
            run_id=run_id, trigger=trigger, error_type=type(error).__name__, error_message=str(error),
            detail={"role": "last_resort"},
        )
        logger.warning(
            "历史日线获取失败 provider=akshare_last_resort symbol=%s error_type=%s elapsed_ms=%s",
            symbol, type(error).__name__, round((time.monotonic() - started) * 1000),
        )
        return []


def _refresh_range_local_first(self, store, symbol: str, start: str, end: str, trigger=None, run_id=None) -> int:
    """Remote phase for a missing A-share range; local-gap detection stays in refresh()."""
    symbol = symbol.strip().upper()
    if self._kind(symbol) != "a":
        return _ORIGINAL_REFRESH_RANGE(self, store, symbol, start, end, trigger=trigger, run_id=run_id)

    overall_started = _price_history.beijing_now().isoformat()
    overall_mono = time.monotonic()
    providers: list[str] = []

    providers.append("tencent")
    bars = self._tencent_bars(store, symbol, start, end, trigger=trigger, run_id=run_id)
    if not bars:
        providers.append("tushare")
        bars = self._tushare_bars(store, symbol, start, end, trigger=trigger, run_id=run_id)
    if not bars:
        providers.append("akshare")
        bars = _eastmoney_a_bars(self, store, symbol, start, end, trigger=trigger, run_id=run_id)
    if not bars:
        self._record_attempt(
            store, symbol=symbol, provider="overall", status="error",
            started_at=overall_started, elapsed_ms=round((time.monotonic() - overall_mono) * 1000),
            run_id=run_id, trigger=trigger,
            error_type="PriceHistoryUnavailable", error_message="all_qfq_providers_failed",
            detail={"providers": providers, "contract": "iso-qfq-v1"},
        )
        raise _price_history.PriceHistoryUnavailable(
            "历史日线不可用：Tencent、Tushare qfq、Eastmoney 均未返回可用数据。"
        )

    self._append_sina_closing_bar(symbol, bars, store=store, trigger=trigger, run_id=run_id)
    store.save_daily_prices(symbol, bars)
    self._record_attempt(
        store, symbol=symbol, provider="overall", status="ok",
        started_at=overall_started, elapsed_ms=round((time.monotonic() - overall_mono) * 1000),
        run_id=run_id, trigger=trigger, bar_count=len(bars),
        detail={"providers": providers, "contract": "iso-qfq-v1"},
    )
    return len(bars)


def install() -> None:
    """Install the policy once, before PortfolioStore/PriceHistoryService instances exist."""
    global _INSTALLED
    if _INSTALLED:
        return
    _storage.PortfolioStore.__init__ = _store_init
    _storage.PortfolioStore.save_daily_prices = _save_daily_prices
    _storage.PortfolioStore.replace_daily_prices = _replace_daily_prices
    _price_history.PriceHistoryService._tencent_bars = _tencent_bars
    _price_history.PriceHistoryService._tushare_bars = _tushare_bars_qfq
    _price_history.PriceHistoryService._append_sina_closing_bar = _sina_closing_bar
    _price_history.PriceHistoryService._refresh_range = _refresh_range_local_first
    _INSTALLED = True
