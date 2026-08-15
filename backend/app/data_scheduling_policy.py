"""Session-aware Local-First scheduling for provider-backed market data.

This module is installed from the v2 bootstrap after the quarantined legacy
application has constructed its services. It narrows *when* provider calls are
allowed without changing ActionPolicy, candidate selection, sizing, or execution
semantics.

Goals:
- no automatic startup provider calls while exchanges are closed;
- quote collection stays trading-session oriented;
- daily-history catch-up fetches only when a completed session is actually
  missing, with a conservative retry budget;
- the 24h history-backfill loop becomes a cheap no-op outside a bounded
  post-close maintenance window;
- broad-market regime is persisted once per completed CN session and reused by
  every DecisionContext.
"""
from __future__ import annotations

import time
from typing import Iterable


MARKET_REGIME_CACHE_KEY = "market_regime"
MIN_HISTORY_RETRY_SECONDS = 30 * 60
POST_CLOSE_MAINTENANCE_MINUTES = 90


def _normalized(symbols: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))


def _market_open(m, symbol: str, now) -> bool:
    return m.trading_calendar.is_symbol_market_open(symbol, moment=now)


def _post_close_maintenance(m, symbol: str, now) -> bool:
    market = m.trading_calendar.market_for_symbol(symbol)
    return bool(
        market
        and m.trading_calendar.is_post_close_maintenance_window(
            market,
            now,
            minutes=POST_CLOSE_MAINTENANCE_MINUTES,
        )
    )


def _latest_completed_session(m, symbol: str, now) -> str | None:
    return m.trading_calendar.latest_completed_symbol_session_date(symbol, moment=now)


def _latest_local_bar_date(m, symbol: str) -> str | None:
    bars = m.store.daily_prices(symbol)
    return str(bars[-1].get("trading_date") or "") or None if bars else None


def _history_refresh_allowed(m, symbol: str, trigger: str, now) -> bool:
    if trigger == "history-backfill":
        return _post_close_maintenance(m, symbol, now)
    if trigger == "scheduler-close-snapshot":
        return _post_close_maintenance(m, symbol, now)
    if trigger in {"scheduler-trading-session", "paper-trading-decision"}:
        return _market_open(m, symbol, now)
    return False


def _catch_up_missing_completed_sessions(m, symbols: list[str], trigger: str, run_id: str | None) -> None:
    """Fetch once only when local daily bars lag the latest completed session."""
    now = m.beijing_now()
    for symbol in _normalized(symbols):
        expected = _latest_completed_session(m, symbol, now)
        latest = _latest_local_bar_date(m, symbol)
        if not expected or latest == expected or (latest and latest > expected):
            continue
        if not _history_refresh_allowed(m, symbol, trigger, now):
            continue

        persisted_retry = 0
        try:
            persisted_retry = int(m._daily_history_retry_seconds_left(symbol))
        except Exception:
            persisted_retry = 0
        in_memory_retry = max(0, round(m.daily_history_retry_after.get(symbol, time.monotonic()) - time.monotonic()))
        if persisted_retry > 0 or in_memory_retry > 0:
            continue

        try:
            m.logger.info(
                "daily history completed-session catch-up trigger=%s symbol=%s local=%s expected=%s",
                trigger,
                symbol,
                latest or "none",
                expected,
            )
            m.price_history_service.refresh(m.store, symbol, trigger=trigger, run_id=run_id)
            m.daily_history_refreshed_for[symbol] = expected
            m.daily_history_retry_after.pop(symbol, None)
        except m.PriceHistoryUnavailable as error:
            retry_seconds = max(int(m.DAILY_HISTORY_RETRY_SECONDS), MIN_HISTORY_RETRY_SECONDS)
            m.daily_history_retry_after[symbol] = time.monotonic() + retry_seconds
            m.logger.warning(
                "daily history catch-up failed trigger=%s symbol=%s expected=%s retry_after_seconds=%s error=%s",
                trigger,
                symbol,
                expected,
                retry_seconds,
                error,
            )


def install(m) -> None:
    """Install scheduling guards on the already constructed legacy services."""
    if getattr(m, "_data_scheduling_policy_installed", False):
        return
    m._data_scheduling_policy_installed = True

    original_refresh_quote_cache = m.refresh_quote_cache
    original_refresh_derived_cache = m.refresh_derived_cache
    original_refresh_market_intelligence = m.refresh_market_intelligence
    original_resume_background_work = m.resume_background_work
    original_regime_assess = m.market_regime_service.assess

    def refresh_quote_cache(symbols, force_refresh=False, trigger="scheduled", *args, **kwargs):
        requested = _normalized(symbols)
        if trigger == "startup-prewarm":
            now = m.beijing_now()
            requested = [symbol for symbol in requested if _market_open(m, symbol, now)]
            if not requested:
                m.logger.info("startup quote prewarm skipped: all requested exchanges are closed")
                return m.store.cached_quotes(_normalized(symbols))
        return original_refresh_quote_cache(requested, force_refresh, trigger, *args, **kwargs)

    def refresh_derived_cache(symbols, trigger, force_history=False, run_id=None):
        requested = _normalized(symbols)
        now = m.beijing_now()
        if trigger == "startup-prewarm":
            requested = [symbol for symbol in requested if _market_open(m, symbol, now)]
            if not requested:
                m.logger.info("startup derived-data prewarm skipped: all requested exchanges are closed")
                return None

        # Legacy force_history used to imply a provider attempt, but the desired
        # contract is now coverage/session based. Catch up only a genuinely
        # missing completed session, then let the legacy function recompute risk
        # and technical data locally from persisted bars.
        _catch_up_missing_completed_sessions(m, requested, trigger, run_id)
        if trigger in {"paper-trading-decision", "scheduler-close-snapshot", "history-backfill"}:
            force_history = False

        if trigger == "history-backfill":
            requested = [symbol for symbol in requested if _post_close_maintenance(m, symbol, now)]
            if not requested:
                m.logger.info("history backfill skipped outside post-close maintenance window")
                return None

        return original_refresh_derived_cache(requested, trigger, force_history=force_history, run_id=run_id)

    def assess_market_regime():
        """Persist/reuse one broad-market regime snapshot per completed CN session."""
        now = m.beijing_now()
        expected = m.trading_calendar.latest_completed_session_date("CN", now)
        cached = m.store.cached_market_intelligence(MARKET_REGIME_CACHE_KEY) or {}
        if cached.get("status") == "ready" and cached.get("as_of") == expected:
            return cached

        can_refresh = (
            m.trading_calendar.is_market_open("CN", now)
            or m.trading_calendar.is_post_close_maintenance_window(
                "CN",
                now,
                minutes=POST_CLOSE_MAINTENANCE_MINUTES,
            )
        )
        if not can_refresh:
            if cached:
                return cached
            return {
                "status": "unavailable",
                "regime": "unknown",
                "indexes": [],
                "source": "market_regime_local_cache",
                "as_of": expected,
                "retrieved_at": now.isoformat(),
                "note": "休市期间不自动访问远端；等待下一交易时段或收盘维护窗口刷新。",
            }

        result = dict(original_regime_assess())
        result["as_of"] = expected
        result["retrieved_at"] = now.isoformat()
        if result.get("status") == "ready" and result.get("regime") not in {None, "unknown"}:
            m.store.save_market_intelligence(MARKET_REGIME_CACHE_KEY, result)
            return result
        if cached:
            return cached
        return result

    def startup_market_intelligence() -> None:
        now = m.beijing_now()
        if not (
            m.trading_calendar.is_market_open("CN", now)
            or m.trading_calendar.is_market_open("HK", now)
        ):
            m.logger.info("startup market-intelligence refresh skipped: exchanges are closed")
            return None
        return original_refresh_market_intelligence()

    def resume_background_work() -> None:
        # The original callback captures refresh_market_intelligence as a Thread
        # target. Temporarily substitute the startup-only guarded target; the
        # function object remains captured after this global is restored.
        saved = m.refresh_market_intelligence
        m.refresh_market_intelligence = startup_market_intelligence
        try:
            return original_resume_background_work()
        finally:
            m.refresh_market_intelligence = saved

    m.refresh_quote_cache = refresh_quote_cache
    m.refresh_derived_cache = refresh_derived_cache
    m.market_regime_service.assess = assess_market_regime
    m.resume_background_work = resume_background_work

    # FastAPI registered the original callback during legacy-module import.
    # Replace only that exact function object; do not mutate route tables.
    startup_handlers = getattr(m.app.router, "on_startup", [])
    for index, handler in enumerate(list(startup_handlers)):
        if handler is original_resume_background_work:
            startup_handlers[index] = resume_background_work
