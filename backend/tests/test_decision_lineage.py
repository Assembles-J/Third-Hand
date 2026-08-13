from app.storage import PortfolioStore


def test_context_lineage_appends_snapshots_and_shadow_features(tmp_path):
    store = PortfolioStore(tmp_path / "lineage.db")
    context = {"context_id": "ctx-1", "symbol": "600519", "generated_at": "2026-08-13T15:00:00+08:00",
               "quote": {"price": 10, "as_of": "2026-08-13"}, "daily_bars": {"count": 60, "last_trading_date": "2026-08-13"},
               "risk": {"historical_downside_probability": 10, "annualized_volatility_percent": 20},
               "market_regime": {"regime": "mixed"},
               "technical": {"trend": "up", "sma20": 10, "sma60": 9, "rsi14": 55, "macd_histogram": 1, "atr_percent": 2}}

    store.capture_decision_lineage(context)
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM raw_data_snapshots").fetchone()[0] == 4
        assert connection.execute("SELECT COUNT(*) FROM feature_values WHERE context_id='ctx-1'").fetchone()[0] == 8
        assert connection.execute("SELECT COUNT(*) FROM feature_catalog WHERE enabled=0").fetchone()[0] == 8


def test_lineage_records_quality_events_without_changing_snapshots(tmp_path):
    store = PortfolioStore(tmp_path / "quality-events.db")
    context = {"context_id": "ctx-2", "symbol": "600519", "generated_at": "2026-08-13T15:00:00+08:00",
               "data_quality": {"missing_fields": ["quote.price"], "stale_fields": ["risk"]},
               "quote": None, "daily_bars": None, "risk": None, "market_regime": None, "technical": {}}

    store.capture_decision_lineage(context)

    assert {event["payload"]["field"] for event in store.data_quality_events("600519")} == {"quote.price", "risk"}
