from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.data_scheduling_policy import install


BJ = timezone(timedelta(hours=8))


def test_runtime_wrapper_preserves_market_parameter_and_scoped_cache():
    now = datetime(2026, 8, 18, 11, 0, tzinfo=BJ)
    calls = []

    class Store:
        def __init__(self):
            self.values = {}

        def cached_market_intelligence(self, key):
            return self.values.get(key)

        def save_market_intelligence(self, key, payload):
            self.values[key] = dict(payload)

        def cached_quotes(self, symbols):
            return []

        def daily_prices(self, symbol):
            return []

    class Calendar:
        @staticmethod
        def market_for_symbol(symbol):
            return "HK"

        @staticmethod
        def is_symbol_market_open(symbol, moment=None):
            return True

        @staticmethod
        def is_market_open(market, moment=None):
            return market == "HK"

        @staticmethod
        def is_post_close_maintenance_window(market, moment=None, minutes=90):
            return False

        @staticmethod
        def latest_completed_symbol_session_date(symbol, moment=None):
            return "2026-08-17"

        @staticmethod
        def latest_completed_session_date(market, moment=None):
            assert market == "HK"
            return "2026-08-17"

    def assess_regime(market="CN"):
        calls.append(market)
        return {
            "status": "ready",
            "regime": "mixed",
            "market": market,
            "source": "fixture",
            "indexes": [],
        }

    def resume_background_work():
        return None

    store = Store()
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
        store=store,
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
    first = module.market_regime_service.assess("HK")
    second = module.market_regime_service.assess("HK")

    assert calls == ["HK"]
    assert first["market"] == "HK"
    assert first["as_of"] == "2026-08-17"
    assert second == first
    assert store.values["market_regime:HK"]["market"] == "HK"
    assert "market_regime" not in store.values
