"""Compatibility shim for legacy/test provider surfaces.

Production AKShare 1.18.91 exposes ``stock_zh_a_hist_tx`` and Tushare 1.4.29
exposes ``pro_bar``.  Older installations and existing unit-test stubs may only
expose the historical Eastmoney/Tushare ``pro_api().daily`` surfaces.  In that
case, preserve the pre-policy refresh implementation instead of failing merely
because the newer provider function is absent.

This shim is capability-based, not environment-based: current production keeps
the Tencent-first/qfq policy, while genuinely older provider packages degrade to
the previous behavior until dependencies are upgraded.
"""
from __future__ import annotations

from types import MethodType

from app import daily_history_policy as policy
from app import price_history

_INSTALLED = False
_POLICY_REFRESH_RANGE = price_history.PriceHistoryService._refresh_range


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

    # Existing Beijing-market fixtures and older Tushare builds may expose only
    # pro_api().daily. Temporarily bind the original fallback for this call so
    # legacy capability still works without changing current production routing.
    if self._is_beijing_symbol(symbol):
        try:
            import tushare as ts
        except ImportError:
            ts = None
        if ts is not None and not hasattr(ts, "pro_bar") and hasattr(ts, "pro_api"):
            had_instance_override = "_tushare_bars" in self.__dict__
            previous = self.__dict__.get("_tushare_bars")
            self._tushare_bars = MethodType(policy._ORIGINAL_TUSHARE_BARS, self)
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
