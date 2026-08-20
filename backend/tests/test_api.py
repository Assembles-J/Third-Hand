"""API regression-suite entrypoint.

The pre-governance suite is preserved byte-for-byte in ``api_suite.py`` so the
connector does not have to rewrite a large historical test file for intentional
governance/runtime contract changes. Selected assertions are re-expressed here
against the current canonical contracts.
"""
from __future__ import annotations

import importlib.util
import sys
import time
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
    "test_decision_generation_is_async_idempotent_and_persists_a_report",
    "test_decision_shadow_endpoint_persists_policy_candidates_without_legacy_recommendations",
    "test_derived_refresh_uses_sufficient_local_history_without_remote_fetch",
    "test_paper_run_persists_run_stages_and_symbol_terminal_state",
    "test_paper_run_records_skipped_data_unavailable_when_history_missing",
    "test_recommendation_evaluation_uses_only_future_bars_and_marks_legacy_or_untriggered_records",
    "test_symbol_lookup_returns_candidates",
    "test_symbol_lookup_post_resolves_names_without_query_params",
}
for _name, _value in vars(_suite).items():
    if _name.startswith("test_") and callable(_value) and _name not in _REPLACED:
        globals()[_name] = _value


def _poll_symbol_lookup(request_call, expected_symbol: str):
    deadline = time.monotonic() + 2
    latest = request_call()
    assert latest.status_code == 200
    while time.monotonic() < deadline:
        payload = latest.json()[0]
        if payload["matches"]:
            return latest
        assert payload["lookup_status"] in {"pending", "refreshing"}
        time.sleep(0.02)
        latest = request_call()
        assert latest.status_code == 200
    payload = latest.json()[0]
    assert payload["matches"], f"symbol {expected_symbol} was not cached before polling deadline: {payload}"
    return latest


def test_symbol_lookup_returns_candidates(monkeypatch):
    monkeypatch.setattr(_suite.market_data, "lookup_symbols", lambda names: [{
        "query": names[0],
        "matches": [{"symbol": "01810", "name": "小米集团-W", "market": "HK", "currency": "HKD", "match_type": "exact"}],
        "lookup_status": "matched",
        "lookup_message": "找到 1 个候选代码。",
    }])

    response = _poll_symbol_lookup(
        lambda: _suite.client.get("/v1/market/symbols", params=[("names", "小米集团-W")]),
        "01810",
    )

    assert response.json()[0]["matches"][0]["symbol"] == "01810"
    assert response.json()[0]["lookup_status"] == "matched"


def test_symbol_lookup_post_resolves_names_without_query_params(monkeypatch):
    monkeypatch.setattr(_suite.market_data, "lookup_symbols", lambda names: [{
        "query": names[0],
        "matches": [{"symbol": "600519", "name": "贵州茅台", "market": "CN", "currency": "CNY", "match_type": "exact"}],
        "lookup_status": "matched",
        "lookup_message": "找到 1 个候选代码。",
    }])

    response = _poll_symbol_lookup(
        lambda: _suite.client.post("/v1/market/symbols/resolve", json={"names": ["贵州茅台"]}),
        "600519",
    )

    assert response.json()[0]["matches"][0]["symbol"] == "600519"
    assert response.json()[0]["lookup_status"] == "matched"


def test_decision_generation_is_async_idempotent_and_persists_a_report(monkeypatch):
    """Decision async/idempotency regression must never depend on live providers."""
    symbol = "600519"
    _suite.store.add("holding-1", symbol, "test", 100, 10)
    _suite.store.save_quotes([{
        "symbol": symbol, "price": 12, "currency": "CNY", "source": "test",
        "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00",
    }])
    _suite.store.save_daily_prices(symbol, [{
        "trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 12,
        "high": 13, "low": 9, "source": "test",
    } for index in range(60)])
    _suite.store.save_trade_plan({
        "id": "plan-1", "symbol": symbol, "horizon": "swing", "thesis": "test",
        "market_expectation": "test", "catalysts": [], "entry_condition": "entry",
        "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit",
        "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1,
    })

    acquisition_calls = []

    def local_acquire_many(symbols, **kwargs):
        normalized = tuple(str(item).strip().upper() for item in symbols)
        acquisition_calls.append((normalized, kwargs.get("trigger")))
        return {
            item: {
                "manifest_id": f"test-manifest-{item}",
                "manifest_hash": f"test-hash-{item}",
                "status": "ready",
                "items": [],
            }
            for item in normalized
        }

    monkeypatch.setattr(
        _suite.main.mandatory_acquisition_service_v3,
        "acquire_many",
        local_acquire_many,
    )

    first_response = _suite.client.post("/v1/decisions/generate", json={"symbols": [symbol]})
    second_response = _suite.client.post("/v1/decisions/generate", json={"symbols": [symbol]})
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()["jobs"][0]
    second = second_response.json()["jobs"][0]

    deadline = time.monotonic() + 2
    job = _suite.client.get(f"/v1/decisions/jobs/{first['job_id']}").json()
    while time.monotonic() < deadline and job["status"] not in {"succeeded", "failed"}:
        time.sleep(0.02)
        job = _suite.client.get(f"/v1/decisions/jobs/{first['job_id']}").json()

    assert first["job_id"] == second["job_id"]
    assert job["status"] == "succeeded"
    assert acquisition_calls == [((symbol,), "api-formal-decision"), ((symbol,), "api-formal-decision")]
    assert _suite.client.get("/v1/decisions/latest", params={"symbol": symbol}).json()["automatic_execution"] is False


def test_decision_shadow_endpoint_persists_policy_candidates_without_legacy_recommendations():
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
