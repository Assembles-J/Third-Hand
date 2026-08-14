"""API regression-suite entrypoint.

The pre-governance suite is preserved byte-for-byte in ``api_suite.py`` so the
connector does not have to rewrite a large test file for one intentional policy
version bump. All existing tests are re-exported except the version assertion
below, which now follows the canonical version constant.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from app import decision_config as config


_suite_path = Path(__file__).with_name("api_suite.py")
_spec = importlib.util.spec_from_file_location("third_hand_api_suite", _suite_path)
assert _spec is not None and _spec.loader is not None
_suite = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _suite
_spec.loader.exec_module(_suite)

setup_function = _suite.setup_function

_REPLACED = "test_decision_shadow_endpoint_persists_policy_candidates_without_replacing_recommendations"
for _name, _value in vars(_suite).items():
    if _name.startswith("test_") and callable(_value) and _name != _REPLACED:
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
