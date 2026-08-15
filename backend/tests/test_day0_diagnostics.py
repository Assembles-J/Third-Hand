from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.admin.router import create_admin_diagnostics_router
from app.application_services.admin.day0_diagnostics import Day0DiagnosticsService


class FakeStore:
    def simulation_runs(self, limit=1):
        return [{
            "run_id": "run-1",
            "trigger": "manual",
            "started_at": "2026-08-15T09:00:00+08:00",
            "finished_at": "2026-08-15T09:00:05+08:00",
            "status": "completed",
            "symbol_count": 2,
            "generated": 2,
            "executed": 0,
            "skipped": 0,
            "message": "done",
        }]

    def simulation_run(self, run_id):
        assert run_id == "run-1"
        return {
            **self.simulation_runs()[0],
            "stages": [
                {
                    "stage": "candidate_pool",
                    "status": "ok",
                    "symbol": None,
                    "elapsed_ms": 1,
                    "detail": {
                        "candidate_selection_version": "candidate-rotation-v1",
                        "candidate_pool_hash": "poolhash",
                        "rotation_key": "2026-08-15",
                        "eligible_count": 100,
                        "requested_limit": 8,
                        "selected_count": 2,
                        "selection_algorithm": "paper_positions_first_then_sha256_deterministic_rotation",
                        "selection_independent_of": ["watchlist", "news", "llm_output"],
                        "selected_items": [
                            {"symbol": "000001", "rank": 1, "reason": "deterministic_rotation"},
                            {"symbol": "000002", "rank": 2, "reason": "deterministic_rotation"},
                        ],
                        "decision_symbols": ["000001", "000002"],
                        "due_execution_symbols": [],
                    },
                },
                {
                    "stage": "decision",
                    "status": "ok",
                    "symbol": "000001",
                    "elapsed_ms": 120,
                    "detail": {
                        "name": "示例一",
                        "terminal_state": "decision_generated",
                        "decision_id": "decision-1",
                        "action": "WATCH",
                        "data_quality_status": "ready",
                        "candidate_rank": 1,
                        "candidate_selection_reason": "deterministic_rotation",
                        "ai_shadow_action": "OPEN",
                        "ai_shadow_agreement": False,
                        "open_gate_audit": {
                            "permission": "blocked",
                            "positive_evidence_ids": [],
                            "blockers": ["no positive POLICY evidence for OPEN"],
                            "checks": [
                                {"check_id": "action_gate.open", "passed": True},
                                {"check_id": "position.absent", "passed": True},
                                {"check_id": "positive_policy_evidence.present", "passed": False},
                                {"check_id": "market.not_defensive", "passed": True},
                            ],
                        },
                    },
                },
                {
                    "stage": "decision",
                    "status": "ok",
                    "symbol": "000002",
                    "elapsed_ms": 100,
                    "detail": {
                        "name": "示例二",
                        "terminal_state": "decision_generated",
                        "decision_id": "decision-2",
                        "action": "WATCH",
                        "data_quality_status": "ready",
                        "open_gate_audit": {
                            "permission": "blocked",
                            "positive_evidence_ids": ["trend.above_sma20"],
                            "blockers": ["market.defensive blocks OPEN"],
                            "checks": [
                                {"check_id": "positive_policy_evidence.present", "passed": True},
                                {"check_id": "market.not_defensive", "passed": False},
                            ],
                        },
                    },
                },
                {
                    "stage": "execution",
                    "status": "skipped",
                    "symbol": "000001",
                    "elapsed_ms": 2,
                    "detail": {
                        "name": "示例一",
                        "terminal_state": "not_due",
                        "decision_id": "decision-1",
                        "action": "WATCH",
                        "reason": "execution_not_due_next_market_session",
                    },
                },
            ],
            "symbols": [],
        }

    def provider_health_summary(self):
        return [{
            "provider": "market_quotes",
            "circuit_state": "closed",
            "consecutive_failures": 0,
            "total_attempts": 10,
            "total_success": 9,
            "total_failures": 1,
            "error_type": "TimeoutError",
            "error_message": "sensitive upstream detail",
            "updated_at": "2026-08-15T09:00:00+08:00",
        }]


def test_day0_diagnostics_summarizes_open_gate_without_mutating():
    payload = Day0DiagnosticsService(FakeStore()).snapshot()

    assert payload["read_only"] is True
    assert payload["latest_run"]["run_id"] == "run-1"
    assert payload["latest_run"]["elapsed_ms"] == 5000
    assert payload["decision_summary"]["action_counts"] == {"WATCH": 2}
    assert payload["open_gate_summary"]["blocked"] == 2
    assert payload["open_gate_summary"]["failed_check_counts"] == {
        "market.not_defensive": 1,
        "positive_policy_evidence.present": 1,
    }
    assert payload["execution_summary"]["reason_counts"] == {
        "execution_not_due_next_market_session": 1,
    }
    assert "error_message" not in payload["provider_health"][0]
    assert payload["parameter_guide"]["actions"]["OPEN"] == "建立新仓位"


def test_day0_diagnostics_router_is_get_only():
    app = FastAPI()
    app.include_router(create_admin_diagnostics_router(Day0DiagnosticsService(FakeStore())))
    client = TestClient(app)

    response = client.get("/v1/admin/day0-diagnostics")
    assert response.status_code == 200
    assert response.json()["generated_from_persisted_audit"] is True

    # Test the public HTTP contract instead of FastAPI's internal route storage,
    # which can change across framework versions while behavior stays identical.
    write_response = client.post("/v1/admin/day0-diagnostics")
    assert write_response.status_code == 405
