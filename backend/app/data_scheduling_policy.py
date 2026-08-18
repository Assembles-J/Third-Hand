"""Session-aware Local-First scheduling for provider-backed market data.

This module is installed from the v2 bootstrap after the quarantined legacy
application has constructed its services. It narrows *when* provider calls are
allowed without changing ActionPolicy, candidate selection, sizing, or execution
semantics.

Goals:
- no automatic startup/provider quote calls while exchanges are closed;
- quote/intraday collection stays trading-session oriented;
- daily-history catch-up fetches only when a completed session is actually
  missing, with a conservative retry budget;
- the 24h history-backfill loop becomes a cheap no-op outside a bounded
  post-close maintenance window;
- research-only news is not fetched by every paper cycle;
- broad whole-market research scans are low-frequency rather than every few
  minutes;
- market regime is cached per explicit market and completed exchange session.
"""
from __future__ import annotations

import time
from typing import Iterable


MARKET_REGIME_CACHE_KEY = "market_regime"
MARKET_REGIME_SCOPED_CACHE_PREFIX = "market_regime:"
MIN_HISTORY_RETRY_SECONDS = 30 * 60
MIN_UNIVERSE_SCAN_INTERVAL_SECONDS = 30 * 60
POST_CLOSE_MAINTENANCE_MINUTES = 90

# These triggers are automatic/cache-refresh paths. Closed-market requests must
# consume the persisted quote/intraday snapshot rather than calling a provider.
_SESSION_ONLY_QUOTE_TRIGGERS = frozenset({
    "startup-prewarm",
    "request-forced",
    "holding-created",
    "holding-updated",
    "scheduler-trading-session",
    "paper-trading-decision",
})


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


def _quote_refresh_symbols(m, symbols: Iterable[str], trigger: str, now) -> list[str]:
    """Return symbols for which a provider quote call is currently justified."""
    requested = _normalized(symbols)
    if trigger == "scheduler-close-snapshot":
        return [symbol for symbol in requested if _post_close_maintenance(m, symbol, now)]
    if trigger in _SESSION_ONLY_QUOTE_TRIGGERS:
        return [symbol for symbol in requested if _market_open(m, symbol, now)]
    # Unknown/manual maintenance triggers retain their historical explicit
    # behavior. Public read endpoints do not use those trigger names.
    return requested


def _latest_completed_session(m, symbol: str, now) -> str | None:
    return m.trading_calendar.latest_completed_symbol_session_date(symbol, moment=now)


def _latest_local_bar_date(m, symbol: str) -> str | None:
    bars = m.store.daily_prices(symbol)
    return (str(bars[-1].get("trading_date") or "") or None) if bars else None


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

    original_fetch_and_store_quotes = m.fetch_and_store_quotes
    original_refresh_quote_cache = m.refresh_quote_cache
    original_refresh_intraday_cache = m.refresh_intraday_cache
    original_refresh_derived_cache = m.refresh_derived_cache
    original_refresh_market_intelligence = m.refresh_market_intelligence
    original_resume_background_work = m.resume_background_work
    original_regime_assess = m.market_regime_service.assess

    # Whole-market sectors/top movers are RESEARCH_ONLY and are explicitly
    # excluded from deterministic formal candidate selection. Keep them useful
    # for UI/research, but do not download them every five minutes.
    m.MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS = max(
        int(m.MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS),
        MIN_UNIVERSE_SCAN_INTERVAL_SECONDS,
    )

    def fetch_and_store_quotes(
        symbols,
        *,
        force_refresh,
        trigger,
        run_id=None,
    ):
        requested = _normalized(symbols)
        now = m.beijing_now()
        refreshable = _quote_refresh_symbols(m, requested, str(trigger), now)
        if not refreshable:
            m.logger.info(
                "quote provider refresh skipped local_first=true trigger=%s market_open=false symbols=%s",
                trigger,
                ",".join(requested) or "none",
            )
            if run_id:
                m._record_simulation_stage(
                    run_id,
                    "market_quotes",
                    "skipped",
                    detail={
                        "reason": "closed_market_local_snapshot",
                        "requested": len(requested),
                        "remote_requested": 0,
                    },
                )
            return m.store.cached_quotes(requested)
        return original_fetch_and_store_quotes(
            refreshable,
            force_refresh=force_refresh,
            trigger=trigger,
            run_id=run_id,
        )

    def refresh_quote_cache(symbols, force_refresh=False, trigger="scheduled", *args, **kwargs):
        requested = _normalized(symbols)
        now = m.beijing_now()
        refreshable = _quote_refresh_symbols(m, requested, str(trigger), now)
        if not refreshable:
            m.logger.info(
                "quote/intraday cache refresh skipped local_first=true trigger=%s market_open=false symbols=%s",
                trigger,
                ",".join(requested) or "none",
            )
            return m.store.cached_quotes(requested)
        return original_refresh_quote_cache(refreshable, force_refresh, trigger, *args, **kwargs)

    def refresh_intraday_cache(symbols, trigger):
        requested = _normalized(symbols)
        now = m.beijing_now()
        refreshable = [symbol for symbol in requested if _market_open(m, symbol, now)]
        if not refreshable:
            m.logger.info(
                "intraday provider refresh skipped local_first=true trigger=%s market_open=false symbols=%s",
                trigger,
                ",".join(requested) or "none",
            )
            return None
        return original_refresh_intraday_cache(refreshable, trigger)

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

        result = original_refresh_derived_cache(requested, trigger, force_history=force_history, run_id=run_id)

        # Deterministic research prewarm is allowed to bootstrap a bounded local
        # history set, but an unhealthy provider must not be retried every five
        # minutes. Extend legacy failures to the same conservative 30-minute
        # retry floor used by completed-session catch-up.
        if "history-prewarm" in str(trigger):
            current = time.monotonic()
            for symbol in requested:
                retry_at = float(m.daily_history_retry_after.get(symbol, 0.0) or 0.0)
                if retry_at > current:
                    m.daily_history_retry_after[symbol] = max(
                        retry_at,
                        current + MIN_HISTORY_RETRY_SECONDS,
                    )
        return result

    def refresh_paper_market_intelligence(symbols, names) -> None:
        # News/event inputs are RESEARCH_ONLY and do not participate in formal
        # ActionPolicy. Paper cycles therefore consume the persisted content
        # cache and never create an automatic remote-news request every interval.
        m.logger.info(
            "paper research intelligence remote refresh skipped local_first=true symbols=%s",
            ",".join(_normalized(symbols)) or "none",
        )
        return None

    def _call_original_regime_assess(market: str) -> dict[str, object]:
        """Call the market-aware service while keeping old injected CN adapters usable."""
        try:
            return dict(original_regime_assess(market))
        except TypeError:
            if market != "CN":
                return {
                    "status": "unavailable",
                    "regime": "unknown",
                    "market": market,
                    "indexes": [],
                    "source": "market_regime_unconfigured",
                    "note": f"{market} 市场环境适配器尚未支持显式市场参数。",
                }
            return dict(original_regime_assess())

    def assess_market_regime(market: str = "CN"):
        """Persist/reuse one regime snapshot per explicit market and completed session."""
        normalized = str(market or "CN").strip().upper()
        now = m.beijing_now()
        expected = m.trading_calendar.latest_completed_session_date(normalized, now)
        scoped_key = f"{MARKET_REGIME_SCOPED_CACHE_PREFIX}{normalized}"
        scoped_cached = m.store.cached_market_intelligence(scoped_key) or {}
        legacy_cached = m.store.cached_market_intelligence(MARKET_REGIME_CACHE_KEY) or {} if normalized == "CN" else {}
        cached = scoped_cached or legacy_cached
        if cached.get("status") == "ready" and cached.get("as_of") == expected:
            value = dict(cached)
            value.setdefault("market", normalized)
            return value

        can_refresh = (
            m.trading_calendar.is_market_open(normalized, now)
            or m.trading_calendar.is_post_close_maintenance_window(
                normalized,
                now,
                minutes=POST_CLOSE_MAINTENANCE_MINUTES,
            )
        )
        if not can_refresh:
            if cached:
                value = dict(cached)
                value.setdefault("market", normalized)
                return value
            return {
                "status": "unavailable",
                "regime": "unknown",
                "market": normalized,
                "indexes": [],
                "source": "market_regime_local_cache",
                "as_of": expected,
                "retrieved_at": now.isoformat(),
                "note": "休市期间不自动访问远端；等待下一交易时段或收盘维护窗口刷新。",
            }

        result = _call_original_regime_assess(normalized)
        result["market"] = normalized
        result["as_of"] = expected
        result["retrieved_at"] = now.isoformat()
        if result.get("status") == "ready" and result.get("regime") not in {None, "unknown"}:
            m.store.save_market_intelligence(scoped_key, result)
            # Keep the historical generic CN key during the migration so old
            # diagnostics/snapshots continue to work. Non-CN data is never
            # written there, preventing cross-market fallback.
            if normalized == "CN":
                m.store.save_market_intelligence(MARKET_REGIME_CACHE_KEY, result)
            return result
        if cached:
            value = dict(cached)
            value.setdefault("market", normalized)
            return value
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

    m.fetch_and_store_quotes = fetch_and_store_quotes
    m.refresh_quote_cache = refresh_quote_cache
    m.refresh_intraday_cache = refresh_intraday_cache
    m.refresh_derived_cache = refresh_derived_cache
    m.refresh_paper_market_intelligence = refresh_paper_market_intelligence
    m.market_regime_service.assess = assess_market_regime
    m.resume_background_work = resume_background_work

    # FastAPI registered the original callback during legacy-module import.
    # Replace only that exact function object; do not mutate route tables.
    startup_handlers = getattr(m.app.router, "on_startup", [])
    for index, handler in enumerate(list(startup_handlers)):
        if handler is original_resume_background_work:
            startup_handlers[index] = resume_background_work
