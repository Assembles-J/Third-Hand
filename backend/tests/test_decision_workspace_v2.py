from app.application_services.decision.workspace import DecisionWorkspaceService


class _Store:
    def __init__(self):
        self._reports = [
            {
                "decision_id": "d2",
                "symbol": "600000",
                "name": "Example Bank",
                "generated_at": "2026-08-19T14:00:00+08:00",
                "formal_action": "HOLD",
                "summary": "continuity preserved",
                "strategy": {"strategy_id": "SWING_V1", "strategy_version": "1.0.0"},
                "timeframe_authority": {"policy_version": "multi-timeframe-action-v1"},
                "data_quality": {
                    "status": "ready",
                    "score_percent": 100,
                    "missing_fields": [],
                    "stale_fields": [],
                    "warnings": [],
                },
                "decision_memory": {
                    "prior_decision_id": "d1",
                    "input_changed": True,
                    "material_change": False,
                    "material_change_reason": "continuity_preserved_prior_action",
                    "material_change_components": [],
                    "position_age": 3,
                    "cooldown_until": None,
                    "review_after": "2026-08-20T10:00:00+08:00",
                    "invalidation_conditions": ["close below support"],
                    "continuity_policy_version": "decision-continuity-v2",
                },
            },
            {
                "decision_id": "d1",
                "symbol": "600000",
                "formal_action": "HOLD",
            },
        ]

    def decision_reports(self, symbol, limit):
        assert symbol == "600000"
        return self._reports[:limit]

    def paper_account(self):
        return {
            "positions": [
                {
                    "symbol": "600000",
                    "quantity": 1000.0,
                    "sellable_quantity": 600.0,
                    "locked_quantity": 400.0,
                    "next_eligible_sell_at": "2026-08-20T09:30:00+08:00",
                }
            ]
        }

    def paper_execution_deferrals(self, *, symbol, state, limit):
        assert (symbol, state, limit) == ("600000", "active", 20)
        return [
            {
                "decision_id": "d2",
                "symbol": "600000",
                "action": "EXIT",
                "reason_code": "paper_t1_unsellable_quantity",
                "next_eligible_at": "2026-08-20T09:30:00+08:00",
                "state": "active",
            }
        ]


def test_workspace_composes_existing_decision_memory_and_paper_risk_without_redeciding():
    workspace = DecisionWorkspaceService(_Store()).latest("600000")

    assert workspace["formal_action"] == "HOLD"
    assert workspace["strategy"] == {"strategy_id": "SWING_V1", "strategy_version": "1.0.0"}
    assert workspace["what_changed"]["prior_action"] == "HOLD"
    assert workspace["what_changed"]["current_action"] == "HOLD"
    assert workspace["what_changed"]["material_change"] is False
    assert workspace["paper_risk"]["sellable_quantity"] == 600.0
    assert workspace["paper_risk"]["locked_quantity"] == 400.0
    assert workspace["paper_risk"]["active_deferrals"][0]["reason_code"] == "paper_t1_unsellable_quantity"


def test_workspace_raises_for_missing_symbol_or_report():
    service = DecisionWorkspaceService(_Store())
    try:
        service.latest("")
    except ValueError as error:
        assert str(error) == "symbol is required"
    else:
        raise AssertionError("blank symbol must be rejected")

    class EmptyStore(_Store):
        def decision_reports(self, symbol, limit):
            return []

    try:
        DecisionWorkspaceService(EmptyStore()).latest("600000")
    except KeyError:
        pass
    else:
        raise AssertionError("missing latest decision must be a not-found condition")
