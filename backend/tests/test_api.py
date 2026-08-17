"""API regression-suite entrypoint.

The pre-governance suite is preserved byte-for-byte in ``api_suite.py`` so the
connector does not have to rewrite a large historical test file for intentional
governance/runtime contract changes. Selected assertions are re-expressed here
against the current canonical contracts.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from app import decision_config as config
from app.price_history import PriceHistoryUnavailable


_suite_path = Path(__file__).with_name("api_suite.py")
_spec = importlib.util.spec_from_file_location("third_hand_api_suite", _suite_path)
assert _spec is not None and _spec.loader is not None
_suite = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _suite
_spec.loader.exec_module(_suite)

setup_function = _suite.setup_function

_REPLACED = {
    "test_decision_shadow_endpoint_persists_policy_candidates_without_replacing_recommendations",
    "test_derived_refresh_uses_sufficient_local_history_without_remote_fetch",
    "test_paper_run_persists_run_stages_and_symbol_terminal_state",
    "test_paper_run_records_skipped_data_unavailable_when_history_missing",
}
for _name, _value in vars(_suite).items():
    if _name.startswith("test_") and callable(_value) and _name not in _REPLACED:
        globals()[_name] = _value


def test_decision_shadow_endpoint_persists_policy_candidates_without_replacing_recommendations():
    _suite.client.post("/v1/holdings", json={"symbol": "600519", "name": "test", "quantity": 100, "average_cost": 10})
    _suite.store.save_quotes([{
        "symbol": "600519", "price": 12, "currency": "CNY", "source": "test",
        "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00",
    }])
    _suite.store.save_daily_prices("600519", [{
        "trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 12,
        "high": 13, "low": 9, "source": "test",
    } for index in range(60)])
    _suite.store.save_trade_plan({
        "id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test",
        "market_expectation": "test", "catalysts": [], "entry_condition": "entry",
        "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit",
        "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1,
    })

    response = _suite.client.get("/v1/decisions/shadow/600519")

    assert response.status_code == 200
    assert response.json()["shadow_mode"] is True
    assert response.json()["action_candidates"]
    assert response.json()["sizing"] is None
    assert response.json()["policy_version"] == config.ACTION_POLICY_VERSION
    assert _suite.store.shadow_reports("600519")[0]["shadow_id"] == response.json()["shadow_id"]
    assert _suite.client.get("/v1/research-recommendations").json() == []


def test_derived_refresh_uses_sufficient_local_history_without_remote_fetch(monkeypatch):
    class MarketRegimeFixture:
        def assess(self):
            return {"status": "unavailable"}

    symbol = "600519"
    _suite.store.add("holding-1", symbol, "test", 100, 10)
    expected = _suite.date(2026, 8, 14)
    _suite.store.save_daily_prices(symbol, [{
        "trading_date": (expected - _suite.timedelta(days=64 - index)).isoformat(),
        "open": 10 + index,
        "close": 10.5 + index,
        "high": 11 + index,
        "low": 9 + index,
        "source": "local-test",
    } for index in range(65)])
    remote_calls = []
    monkeypatch.setattr(
        _suite.main.price_history_service,
        "refresh",
        lambda *args, **kwargs: remote_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(_suite.main, "market_regime_service", MarketRegimeFixture())
    monkeypatch.setattr(
        _suite.main.trading_calendar,
        "latest_completed_symbol_session_date",
        lambda *_args, **_kwargs: expected.isoformat(),
    )

    _suite.main.refresh_derived_cache([symbol], "paper-trading-decision", force_history=True)

    assert remote_calls == []
    bars = _suite.store.daily_prices(symbol, 100)
    assert len(bars) >= 65
    assert bars[-1]["trading_date"] == expected.isoformat()


def test_paper_run_persists_run_stages_and_symbol_terminal_state(monkeypatch):
    """A closed-market force run must consume the persisted quote, not fetch one."""

    class MarketRegimeFixture:
        def assess(self):
            return {"status": "unavailable"}

    symbol = "600519"
    _suite.store.save_paper_account(100_000)
    start = _suite.date(2026, 4, 1)
    _suite.store.save_daily_prices(symbol, [{
        "trading_date": (start + _suite.timedelta(days=index)).isoformat(),
        "open": 10 + index,
        "close": 10.5 + index,
        "high": 11 + index,
        "low": 9 + index,
        "source": "local-test",
    } for index in range(65)])
    quote = {
        "symbol": symbol,
        "name": "test",
        "price": 1500.0,
        "as_of": "2026-08-14T10:00:00+08:00",
        "retrieved_at": "2026-08-14T10:00:00+08:00",
        "source": "test",
        "change_percent": 1.2,
        "refresh_status": "stored",
    }
    _suite.store.save_quotes([quote])

    remote_quote_calls = []
    monkeypatch.setattr(
        _suite.main.market_data,
        "quotes",
        lambda symbols, force_refresh=False: remote_quote_calls.append(tuple(symbols)) or [dict(quote)],
    )
    monkeypatch.setattr(_suite.main.market_data, "latest_market_snapshot", lambda markets: [])
    monkeypatch.setattr(_suite.main.news_service, "fetch", lambda symbols, names: [])
    monkeypatch.setattr(_suite.main, "market_regime_service", MarketRegimeFixture())
    monkeypatch.setattr(
        _suite.main.trading_calendar,
        "is_symbol_market_open",
        lambda *_args, **_kwargs: False,
    )

    result = _suite.main.run_paper_trading_cycle([symbol], force=True, allow_when_disabled=True)

    assert result["run_id"]
    runs = _suite.store.simulation_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    detail = _suite.store.simulation_run(result["run_id"])
    stages = {stage["stage"] for stage in detail["stages"]}
    # Refresh-detail stages are conditional: if the local snapshot is already
    # sufficient (or another refresh owns the derived-data lock), a successful
    # closed-market run need not manufacture daily/risk refresh rows. The stable
    # audit contract is the candidate lineage, explicit local quote decision,
    # Research-only news stage, formal decision, and final equity snapshot.
    assert {
        "candidate_pool",
        "market_quotes",
        "news",
        "decision",
        "equity_snapshot",
    }.issubset(stages)
    assert detail["symbols"][0]["terminal_state"] == "decision_generated"

    market_quote_stage = next(stage for stage in detail["stages"] if stage["stage"] == "market_quotes")
    assert market_quote_stage["status"] == "skipped"
    assert market_quote_stage["detail"]["reason"] == "closed_market_local_snapshot"
    assert market_quote_stage["detail"]["remote_requested"] == 0

    response = _suite.client.get(f"/v1/paper-trading/runs/{result['run_id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_paper_run_records_skipped_data_unavailable_when_history_missing(monkeypatch):
    class MarketRegimeFixture:
        def assess(self):
            return {"status": "unavailable"}

    symbol = "000001"
    _suite.store.save_paper_account(100_000)
    quote = {
        "symbol": symbol,
        "name": "test",
        "price": 10.0,
        "as_of": "2026-08-17T10:00:00+08:00",
        "retrieved_at": "2026-08-17T10:00:00+08:00",
        "source": "test",
        "change_percent": 0.0,
        "refresh_status": "stored",
    }
    monkeypatch.setattr(_suite.main.market_data, "quotes", lambda symbols, force_refresh=False: [dict(quote)])
    monkeypatch.setattr(_suite.main.market_data, "latest_market_snapshot", lambda markets: [])
    monkeypatch.setattr(_suite.main.news_service, "fetch", lambda symbols, names: [])
    monkeypatch.setattr(_suite.main, "market_regime_service", MarketRegimeFixture())
    monkeypatch.setattr(_suite.main.trading_calendar, "is_symbol_market_open", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        _suite.main.price_history_service,
        "refresh",
        lambda *args, **kwargs: (_ for _ in ()).throw(PriceHistoryUnavailable("test outage")),
    )

    result = _suite.main.run_paper_trading_cycle([symbol], force=True, allow_when_disabled=True)

    detail = _suite.store.simulation_run(result["run_id"])
    symbol_state = next(item for item in detail["symbols"] if item["symbol"] == symbol)
    assert symbol_state["terminal_state"] == "skipped_data_unavailable"
    assert symbol_state["detail"]["reason"] == "insufficient_daily_bars"
    assert not any(
        stage["stage"] == "decision" and stage["symbol"] == symbol and stage["status"] == "ok"
        for stage in detail["stages"]
    )
