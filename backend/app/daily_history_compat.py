"""Compatibility shim for legacy/test provider surfaces.

Production AKShare 1.18.91 exposes ``stock_zh_a_hist_tx`` and Tushare 1.4.29
exposes ``pro_bar``. Older installations and existing unit-test stubs may only
expose the historical Eastmoney/Tushare ``pro_api().daily`` surfaces. In that
case, preserve the previous capability instead of failing merely because the
newer provider function is absent.

This shim is capability-based, not environment-based: current production keeps
the Tencent-first/qfq policy, while genuinely older provider packages degrade to
the previous behavior until dependencies are upgraded.
"""
from __future__ import annotations

import os
from types import MethodType

from app import daily_history_policy as policy
from app import price_history
from app.decimal_utils import decimal_text

_INSTALLED = False
_POLICY_REFRESH_RANGE = price_history.PriceHistoryService._refresh_range


def _legacy_tushare_bars(self, store, symbol: str, start: str, end: str, trigger=None, run_id=None):
    """Compatibility-only implementation for Tushare builds without pro_bar."""
    started_at = price_history.beijing_now().isoformat()
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        self._record_attempt(
            store, symbol=symbol, provider="tushare", status="skipped",
            started_at=started_at, elapsed_ms=0, run_id=run_id, trigger=trigger,
            detail={"reason": "tushare_token_missing"},
        )
        return []
    try:
        import tushare as ts

        exchange = "BJ" if self._is_beijing_symbol(symbol) else (
            "SH" if symbol.startswith(("5", "6", "9")) else "SZ"
        )
        client = ts.pro_api(token)
        frame = client.daily(ts_code=f"{symbol}.{exchange}", start_date=start, end_date=end)
        if frame is None or frame.empty:
            return []
        bars = []
        for _, row in frame.iterrows():
            trading_date = self._trading_date(row.get("trade_date"))
            close = decimal_text(row.get("close"))
            if trading_date is None or close is None:
                continue
            bars.append({
                "trading_date": trading_date,
                "open": decimal_text(row.get("open")),
                "close": close,
                "high": decimal_text(row.get("high")),
                "low": decimal_text(row.get("low")),
                "volume": decimal_text(row.get("vol")),
                "amount": decimal_text(row.get("amount")),
                "adjustment": "provider-default",
                "source": "Tushare daily history",
            })
        if bars:
            self._record_attempt(
                store, symbol=symbol, provider="tushare", status="ok",
                started_at=started_at, elapsed_ms=0, run_id=run_id, trigger=trigger,
                bar_count=len(bars), detail={"compatibility": "legacy_pro_api_daily"},
            )
        return bars
    except Exception as error:
        self._record_attempt(
            store, symbol=symbol, provider="tushare", status="error",
            started_at=started_at, elapsed_ms=0, run_id=run_id, trigger=trigger,
            error_type=type(error).__name__, error_message=str(error),
            detail={"compatibility": "legacy_pro_api_daily"},
        )
        return []


def _refresh_range_compatible(self, store, symbol: str, start: str, end: str, trigger=None, run_id=None):
    symbol = symbol.strip().upper()
    if self._kind(symbol) != "a":
        return _POLICY_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )

    try:
        import akshare as ak
    except ImportError:
        return _POLICY_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )

    # Older AKShare builds/test doubles do not expose the Tencent history
    # interface. Preserve the historical Eastmoney-first path in that case.
    if not hasattr(ak, "stock_zh_a_hist_tx"):
        return policy._ORIGINAL_REFRESH_RANGE(
            self, store, symbol, start, end, trigger=trigger, run_id=run_id
        )

    # Older Tushare builds/test doubles may expose only pro_api().daily for
    # Beijing securities. Bind a compatibility provider only for this call.
    if self._is_beijing_symbol(symbol):
        try:
            import tushare as ts
        except ImportError:
            ts = None
        if ts is not None and not hasattr(ts, "pro_bar") and hasattr(ts, "pro_api"):
            had_instance_override = "_tushare_bars" in self.__dict__
            previous = self.__dict__.get("_tushare_bars")
            self._tushare_bars = MethodType(_legacy_tushare_bars, self)
            try:
                return policy._ORIGINAL_REFRESH_RANGE(
                    self, store, symbol, start, end, trigger=trigger, run_id=run_id
                )
            finally:
                if had_instance_override:
                    self.__dict__["_tushare_bars"] = previous
                else:
                    self.__dict__.pop("_tushare_bars", None)

    return _POLICY_REFRESH_RANGE(
        self, store, symbol, start, end, trigger=trigger, run_id=run_id
    )


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    price_history.PriceHistoryService._refresh_range = _refresh_range_compatible
    _INSTALLED = True
