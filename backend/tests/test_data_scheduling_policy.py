from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from app.data_scheduling_policy import install
from app.decision_context import DecisionContextBuilder
from app.freshness import evaluate_session_freshness
from app.trading_calendar import TradingCalendarService


BJ = timezone(timedelta(hours=8))


def test_completed_session_freshness_keeps_friday_fresh_on_weekend():
    now = datetime(2026, 8, 15, 12, 0, tzinfo=BJ)  # Saturday

    result = evaluate_session_freshness(
        "daily_bars",
        as_of="2026-08-14",
        market="CN",
        now=now,
    )

    assert result.status == "fresh"
    assert result.reason is None


def test_completed_session_freshness_flags_actual_missing_session():
    now = datetime(2026, 8, 15, 12, 0, tzinfo=BJ)  # latest completed CN session is Friday 8/14

    result = evaluate_session_freshness(
        "daily_bars",
        as_of="2026-08-13",
        market="CN",
        now=now,
    )

    assert result.status == "stale"
    assert result.reason == "missing_completed_session:2026-08-14"


def test_calendar_uses_previous_day_during_live_session_and_today_after_close():
    calendar = TradingCalendarService()

    live = calendar.latest_completed_session_date("CN", datetime(2026, 8, 14, 10, 0, tzinfo=BJ))
    closed = calendar.latest_completed_session_date("CN", datetime(2026, 8, 14, 16, 0, tzinfo=BJ))

    assert live == "2026-08-13"
    assert closed == "2026-08-14"


def test_decision_context_can_read_global_persisted_market_regime():
    class Store:
        def cached_market_intelligence(self, key):
            assert key == "market_regime"
            return {
                "status": "ready",
                "regime": "supportive",
                "source": "AKShare index daily",
                "as_of": "2026-08-14",
            }

    snapshot = DecisionContextBuilder(Store())._market_regime(None)

    assert snapshot is not None
    assert snapshot.status == "ready"
    assert snapshot.regime == "supportive"
    assert snapshot.as_of == "2026-08-14"


def test_closed_market_automatic_paths_use_local_snapshots_only():
    now = datetime(2026, 8, 15, 12, 0, tzinfo=BJ)  # Saturday
    calls = {
        "fetch_quotes": 0,
        "quote_cache": 0,
        "intraday": 0,
        "derived": 0,
        "regime": 0,
        "market_intelligence": 0,
        "paper_news": 0,
    }

    class Store:
        def __init__(self):
            self.regime = None

        def cached_quotes(self, symbols):
            return [{"symbol": symbol, "price": 1.0} for symbol in symbols]

        def daily_prices(self, symbol):
            return [{"trading_date": "2026-08-13", "close": 1.0}] * 65

        def cached_market_intelligence(self, key):
            return self.regime if key == "market_regime" else None

        def save_market_intelligence(self, key, payload):
            assert key == "market_regime"
            self.regime = dict(payload)

    class Calendar:
        @staticmethod
        def market_for_symbol(symbol):
            return "CN"

        @staticmethod
        def is_symbol_market_open(symbol, moment=None):
            return False

        @staticmethod
        def is_market_open(market, moment=None):
            return False

        @staticmethod
        def is_post_close_maintenance_window(market, moment=None, minutes=90):
            return False

        @staticmethod
        def latest_completed_symbol_session_date(symbol, moment=None):
            return "2026-08-14"

        @staticmethod
        def latest_completed_session_date(market, moment=None):
            return "2026-08-14"

    def fetch_and_store_quotes(symbols, *, force_refresh, trigger, run_id=None):
        calls["fetch_quotes"] += 1
        return []

    def refresh_quote_cache(symbols, force_refresh=False, trigger="scheduled", *args, **kwargs):
        calls["quote_cache"] += 1
        return []

    def refresh_intraday_cache(symbols, trigger):
        calls["intraday"] += 1

    def refresh_derived_cache(symbols, trigger, force_history=False, run_id=None):
        calls["derived"] += 1

    def refresh_market_intelligence():
        calls["market_intelligence"] += 1

    def refresh_paper_market_intelligence(symbols, names):
        calls["paper_news"] += 1

    def assess_regime():
        calls["regime"] += 1
        return {"status": "ready", "regime": "mixed", "source": "remote"}

    def resume_background_work():
        return None

    module = SimpleNamespace(
        fetch_and_store_quotes=fetch_and_store_quotes,
        refresh_quote_cache=refresh_quote_cache,
        refresh_intraday_cache=refresh_intraday_cache,
        refresh_derived_cache=refresh_derived_cache,
        refresh_market_intelligence=refresh_market_intelligence,
        refresh_paper_market_intelligence=refresh_paper_market_intelligence,
        resume_background_work=resume_background_work,
        market_regime_service=SimpleNamespace(assess=assess_regime),
        trading_calendar=Calendar(),
        store=Store(),
        beijing_now=lambda: now,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        app=SimpleNamespace(router=SimpleNamespace(on_startup=[resume_background_work])),
        daily_history_retry_after={},
        daily_history_refreshed_for={},
        DAILY_HISTORY_RETRY_SECONDS=300,
        MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS=300,
        _daily_history_retry_seconds_left=lambda symbol: 0,
        _record_simulation_stage=lambda *args, **kwargs: None,
        price_history_service=SimpleNamespace(refresh=lambda *args, **kwargs: None),
        PriceHistoryUnavailable=RuntimeError,
    )

    install(module)

    cached = module.refresh_quote_cache(["600519"], True, "startup-prewarm")
    paper_quotes = module.fetch_and_store_quotes(
        ["600519"],
        force_refresh=True,
        trigger="paper-trading-decision",
        run_id="run-1",
    )
    module.refresh_intraday_cache(["600519"], "request-forced")
    module.refresh_derived_cache(["600519"], "history-backfill")
    module.refresh_paper_market_intelligence(["600519"], {"600519": "贵州茅台"})
    regime = module.market_regime_service.assess()

    assert cached[0]["symbol"] == "600519"
    assert paper_quotes[0]["symbol"] == "600519"
    assert calls["fetch_quotes"] == 0
    assert calls["quote_cache"] == 0
    assert calls["intraday"] == 0
    assert calls["derived"] == 0
    assert calls["regime"] == 0
    assert calls["market_intelligence"] == 0
    assert calls["paper_news"] == 0
    assert module.MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS == 1800
    assert regime["status"] == "unavailable"


def test_open_market_quote_and_intraday_paths_are_allowed():
    now = datetime(2026, 8, 14, 10, 0, tzinfo=BJ)
    calls = {"fetch_quotes": 0, "quote_cache": 0, "intraday": 0}

    class Store:
        def cached_quotes(self, symbols):
            return []

        def daily_prices(self, symbol):
            return []

        def cached_market_intelligence(self, key):
            return {"status": "ready", "regime": "mixed", "as_of": "2026-08-13", "source": "cache"} if key == "market_regime" else None

        def save_market_intelligence(self, key, payload):
            pass

    class Calendar:
        @staticmethod
        def market_for_symbol(symbol):
            return "CN"

        @staticmethod
        def is_symbol_market_open(symbol, moment=None):
            return True

        @staticmethod
        def is_market_open(market, moment=None):
            return True

        @staticmethod
        def is_post_close_maintenance_window(market, moment=None, minutes=90):
            return False

        @staticmethod
        def latest_completed_symbol_session_date(symbol, moment=None):
            return "2026-08-13"

        @staticmethod
        def latest_completed_session_date(market, moment=None):
            return "2026-08-13"

    def fetch_and_store_quotes(symbols, *, force_refresh, trigger, run_id=None):
        calls["fetch_quotes"] += 1
        return [{"symbol": symbols[0], "price": 10.0}]

    def refresh_quote_cache(symbols, force_refresh=False, trigger="scheduled", *args, **kwargs):
        calls["quote_cache"] += 1
        return None

    def refresh_intraday_cache(symbols, trigger):
        calls["intraday"] += 1
        return None

    def resume_background_work():
        return None

    module = SimpleNamespace(
        fetch_and_store_quotes=fetch_and_store_quotes,
        refresh_quote_cache=refresh_quote_cache,
        refresh_intraday_cache=refresh_intraday_cache,
        refresh_derived_cache=lambda *args, **kwargs: None,
        refresh_market_intelligence=lambda: None,
        refresh_paper_market_intelligence=lambda *args, **kwargs: None,
        resume_background_work=resume_background_work,
        market_regime_service=SimpleNamespace(assess=lambda: {"status": "ready", "regime": "mixed"}),
        trading_calendar=Calendar(),
        store=Store(),
        beijing_now=lambda: now,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        app=SimpleNamespace(router=SimpleNamespace(on_startup=[resume_background_work])),
        daily_history_retry_after={},
        daily_history_refreshed_for={},
        DAILY_HISTORY_RETRY_SECONDS=300,
        MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS=300,
        _daily_history_retry_seconds_left=lambda symbol: 0,
        _record_simulation_stage=lambda *args, **kwargs: None,
        price_history_service=SimpleNamespace(refresh=lambda *args, **kwargs: None),
        PriceHistoryUnavailable=RuntimeError,
    )

    install(module)
    module.fetch_and_store_quotes(["600519"], force_refresh=True, trigger="paper-trading-decision")
    module.refresh_quote_cache(["600519"], True, "request-forced")
    module.refresh_intraday_cache(["600519"], "request-forced")

    assert calls == {"fetch_quotes": 1, "quote_cache": 1, "intraday": 1}


def test_market_regime_remote_refresh_is_persisted_once_per_completed_session():
    now = datetime(2026, 8, 14, 10, 0, tzinfo=BJ)
    calls = {"regime": 0}

    class Store:
        def __init__(self):
            self.regime = None

        def cached_market_intelligence(self, key):
            return self.regime if key == "market_regime" else None

        def save_market_intelligence(self, key, payload):
            self.regime = dict(payload)

        def cached_quotes(self, symbols):
            return []

        def daily_prices(self, symbol):
            return []

    class Calendar:
        @staticmethod
        def market_for_symbol(symbol):
            return "CN"

        @staticmethod
        def is_symbol_market_open(symbol, moment=None):
            return True

        @staticmethod
        def is_market_open(market, moment=None):
            return market == "CN"

        @staticmethod
        def is_post_close_maintenance_window(market, moment=None, minutes=90):
            return False

        @staticmethod
        def latest_completed_symbol_session_date(symbol, moment=None):
            return "2026-08-13"

        @staticmethod
        def latest_completed_session_date(market, moment=None):
            return "2026-08-13"

    def assess_regime():
        calls["regime"] += 1
        return {"status": "ready", "regime": "supportive", "source": "remote", "indexes": []}

    def resume_background_work():
        return None

    module = SimpleNamespace(
        fetch_and_store_quotes=lambda *args, **kwargs: [],
        refresh_quote_cache=lambda *args, **kwargs: [],
        refresh_intraday_cache=lambda *args, **kwargs: None,
        refresh_derived_cache=lambda *args, **kwargs: None,
        refresh_market_intelligence=lambda: None,
        refresh_paper_market_intelligence=lambda *args, **kwargs: None,
        resume_background_work=resume_background_work,
        market_regime_service=SimpleNamespace(assess=assess_regime),
        trading_calendar=Calendar(),
        store=Store(),
        beijing_now=lambda: now,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        app=SimpleNamespace(router=SimpleNamespace(on_startup=[resume_background_work])),
        daily_history_retry_after={},
        daily_history_refreshed_for={},
        DAILY_HISTORY_RETRY_SECONDS=300,
        MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS=300,
        _daily_history_retry_seconds_left=lambda symbol: 0,
        _record_simulation_stage=lambda *args, **kwargs: None,
        price_history_service=SimpleNamespace(refresh=lambda *args, **kwargs: None),
        PriceHistoryUnavailable=RuntimeError,
    )

    install(module)
    first = module.market_regime_service.assess()
    second = module.market_regime_service.assess()

    assert calls["regime"] == 1
    assert first["as_of"] == "2026-08-13"
    assert second == first
