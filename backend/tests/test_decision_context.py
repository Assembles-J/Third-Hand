from datetime import date, timedelta

from app import decision_config as config
from app.data_quality import summarize_data_quality
from app.decision_context import DecisionContextBuilder
from app.storage import PortfolioStore
from app.time_utils import beijing_now
from app.trading_calendar import TradingCalendarService


def _bars():
    return [{
        "trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 10 + index / 10,
        "high": 11 + index / 10, "low": 9 + index / 10, "source": "test",
    } for index in range(60)]


def _plan():
    return {
        "id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test",
        "market_expectation": "test", "catalysts": [], "entry_condition": "entry",
        "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit",
        "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1,
    }


def _open_gate(result):
    return next(gate for gate in result.action_gates if gate.action == "OPEN")


def _sessions(market: str, count: int = 60) -> list[str]:
    service = TradingCalendarService()
    completed = service.latest_completed_session_date(market, beijing_now())
    assert completed is not None
    end = date.fromisoformat(completed)
    sessions = service.session_dates(
        market,
        (end - timedelta(days=140)).isoformat(),
        completed,
    )
    assert len(sessions) >= count
    return sessions[-count:]


def test_context_builder_has_stable_input_hash_and_does_not_need_an_action(tmp_path):
    store = PortfolioStore(tmp_path / "context.db")
    store.add("holding-1", "600519", "test", 100, 10)
    store.save_available_cash(1000)
    store.save_quotes([{"symbol": "600519", "price": 12, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", _bars())
    store.save_risk({"symbol": "600519", "as_of": "2026-07-31", "sample_count": 60, "historical_downside_probability": 10, "annualized_volatility_percent": 20, "risk_level": "low"})
    store.save_trade_plan(_plan())
    store.save_personal_rule({"id": "rule-1", "scope": "global", "symbol": None, "max_position_percent": 20, "loss_review_percent": 15, "volatility_review_percent": 50, "enabled": True, "version": 1, "updated_at": "2026-07-31T10:00:00+08:00"})
    store.save_instrument_metadata({"symbol": "600519", "market": "CN", "currency": "CNY", "lot_size": 100, "price_tick": "0.01", "source": "test", "as_of": "2026-07-31"})

    first, second = DecisionContextBuilder(store).build(" 600519 "), DecisionContextBuilder(store).build("600519")

    assert first.symbol == "600519"
    assert first.input_hash == second.input_hash
    assert first.position.market_value == 1200
    assert first.data_quality.status == "degraded"
    assert first.data_quality.missing_fields == ()
    assert not hasattr(first, "action")


def test_data_quality_blocks_only_missing_price_and_degrades_non_execution_inputs():
    result = summarize_data_quality(
        has_quote=False, daily_bar_count=59, total_assets_available=False, plan_enabled=False,
        has_risk=False, has_market_regime=False, has_relative_strength=False, has_events=False,
    )

    assert result.status == "blocked"
    assert result.missing_fields == ("quote.price",)
    assert "trade_plan.auto_draft unavailable" in result.warnings
    assert "risk unavailable" in result.warnings


def test_open_gate_uses_formal_market_regime_name_without_duplicate_unknown_blocker():
    now = beijing_now()
    completed = TradingCalendarService().latest_completed_session_date("CN", now)
    assert completed is not None

    result = summarize_data_quality(
        has_quote=True,
        daily_bar_count=60,
        total_assets_available=True,
        plan_enabled=False,
        has_risk=True,
        has_market_regime=False,
        has_relative_strength=False,
        has_events=False,
        has_instrument=True,
        quote_as_of=now.isoformat(),
        quote_retrieved_at=now.isoformat(),
        daily_bar_as_of=completed,
        risk_as_of=completed,
        market_as_of=None,
        market="CN",
    )

    gate = _open_gate(result)
    assert gate.permission == "blocked"
    assert gate.unavailable_fields == ("market_regime",)
    assert all("market_intelligence" not in item for item in gate.unavailable_fields)


def test_existing_but_stale_market_regime_remains_a_hard_open_blocker():
    now = beijing_now()
    completed = TradingCalendarService().latest_completed_session_date("CN", now)
    assert completed is not None

    result = summarize_data_quality(
        has_quote=True,
        daily_bar_count=60,
        total_assets_available=True,
        plan_enabled=False,
        has_risk=True,
        has_market_regime=True,
        has_relative_strength=False,
        has_events=False,
        has_instrument=True,
        quote_as_of=now.isoformat(),
        quote_retrieved_at=now.isoformat(),
        daily_bar_as_of=completed,
        risk_as_of=completed,
        market_as_of="2000-01-03",
        market="CN",
    )

    gate = _open_gate(result)
    assert gate.permission == "blocked"
    assert gate.unavailable_fields == ("market_regime.stale",)
    assert all("market_intelligence" not in item for item in gate.unavailable_fields)


def test_session_aware_freshness_has_a_distinct_audit_version():
    assert config.FRESHNESS_POLICY_VERSION == "freshness-v2-session-aware"


def test_market_identity_and_regime_scope_have_distinct_audit_versions():
    versions = config.audit_version_snapshot()

    assert versions["market_identity_policy_version"] == "market-identity-v2-instrument-authority"
    assert versions["market_regime_policy_version"] == "market-regime-v2-market-scoped"


def test_missing_trade_plan_is_exposed_as_a_non_enabled_editable_draft(tmp_path):
    store = PortfolioStore(tmp_path / "draft-plan.db")
    store.add("holding-1", "600519", "test", 100, 10)
    store.save_available_cash(1000)
    store.save_quotes([{ "symbol": "600519", "price": 10, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00" }])
    store.save_daily_prices("600519", [{"trading_date": f"2026-06-{index + 1:02d}", "open": 10, "close": 10, "high": 11, "low": 9, "source": "test"} for index in range(60)])

    context = DecisionContextBuilder(store).build("600519")

    assert context.trade_plan is not None
    assert context.trade_plan.is_draft is True
    assert context.trade_plan.enabled is False
    assert context.data_quality.status == "degraded"


def test_paper_context_override_uses_simulated_ledger_not_real_holding(tmp_path):
    store = PortfolioStore(tmp_path / "paper-context.db")
    store.add("real-holding", "600519", "real", 900, 8)
    store.save_available_cash(999)
    store.save_quotes([{ "symbol": "600519", "price": 10, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00" }])
    store.save_daily_prices("600519", _bars())

    context = DecisionContextBuilder(store).build(
        "600519",
        holdings_override=[],
        available_cash_override=12_345,
    )

    assert context.position is None
    assert context.account.available_cash == 12_345


def test_hk_context_rejects_cn_regime_and_accepts_market_scoped_hk_regime(tmp_path):
    store = PortfolioStore(tmp_path / "hk-market-scope.db")
    sessions = _sessions("HK")
    completed = sessions[-1]
    now = beijing_now()
    store.save_available_cash(100_000)
    store.save_quotes([{
        "symbol": "01810", "price": 25.88, "currency": "HKD", "source": "test",
        "as_of": completed, "retrieved_at": now.isoformat(),
    }])
    store.save_daily_prices("01810", [{
        "trading_date": session, "open": 25, "close": 25.88, "high": 26, "low": 24.5,
        "source": "test",
    } for session in sessions])
    store.save_risk({
        "symbol": "01810", "as_of": completed, "sample_count": 60,
        "historical_downside_probability": 10, "annualized_volatility_percent": 20,
        "risk_level": "low",
    })
    store.save_instrument_metadata({
        "symbol": "01810", "market": "HK", "currency": "HKD", "lot_size": 200,
        "price_tick": "0.02", "source": "test", "as_of": completed,
    })
    store.save_market_intelligence("market_regime", {
        "status": "ready", "regime": "supportive", "market": "CN",
        "source": "test", "as_of": completed,
    })

    without_hk_regime = DecisionContextBuilder(store).build("01810")

    assert without_hk_regime.instrument.market == "HK"
    assert without_hk_regime.market_regime is None
    assert "market_regime" in _open_gate(without_hk_regime.data_quality).unavailable_fields

    store.save_market_intelligence("market_regime:HK", {
        "status": "ready", "regime": "mixed", "market": "HK",
        "source": "test", "as_of": completed,
    })
    with_hk_regime = DecisionContextBuilder(store).build("01810")

    assert with_hk_regime.market_regime is not None
    assert with_hk_regime.market_regime.regime == "mixed"
    assert with_hk_regime.market_regime.source == "test"


def test_instrument_metadata_market_is_context_authority_over_symbol_shape(tmp_path):
    store = PortfolioStore(tmp_path / "instrument-authority.db")
    store.save_available_cash(1000)
    store.save_instrument_metadata({
        "symbol": "600519", "market": "HK", "currency": "HKD", "lot_size": 100,
        "price_tick": "0.01", "source": "synthetic-migration-test", "as_of": "2026-08-17",
    })
    store.save_market_intelligence("market_regime:HK", {
        "status": "ready", "regime": "mixed", "market": "HK",
        "source": "test", "as_of": "2026-08-17",
    })

    context = DecisionContextBuilder(store).build("600519")

    assert TradingCalendarService.market_for_symbol("600519") == "CN"
    assert context.instrument.market == "HK"
    assert context.market_regime is not None
    assert context.market_regime.regime == "mixed"
