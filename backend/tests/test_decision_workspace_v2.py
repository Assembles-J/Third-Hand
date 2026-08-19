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
                "atomic_evidence_shadow": {
                    "financial_currentness": {
                        "policy_version": "financial-currentness-v1",
                        "latest_observed_period": "2025-12-31",
                        "expected_report_at": "2026-08-20",
                        "latest_period_status": "PENDING_EXPECTED_REPORT",
                        "current_confirmation": "PENDING",
                        "reason_codes": ["earnings_report_pending:2026-08-20"],
                    },
                    "facts": [
                        {
                            "domain": "event",
                            "dimension": "corporate_event",
                            "metric": "event.upcoming.earnings_report.event-results",
                            "source_evidence_id": "event.upcoming.earnings_report.event-results",
                            "value": "2026-08-20",
                            "source_name": "official fixture",
                            "source_reference": "https://example.test/event",
                            "freshness_status": "fresh",
                            "polarity": "NEUTRAL_MATERIAL",
                            "confidence": 0.95,
                        }
                    ],
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

    def cached_market_intelligence(self, key):
        assert key == "corporate_events:600000"
        return {
            "status": "ready",
            "retrieved_at": "2026-08-19T13:50:00+08:00",
            "official_source_status": "ready",
            "events": [
                {
                    "event_id": "event-results",
                    "title": "Example Bank interim results",
                    "event_type": "earnings_report",
                    "scheduled_at": "2026-08-20",
                    "period": "2026 interim",
                    "lifecycle_status": "SCHEDULED",
                    "verification_level": "official",
                    "source": "exchange fixture",
                    "source_rank": 10,
                    "source_reference": "https://example.test/event",
                    "conflict_status": "NONE",
                    "conflict_dates": ["2026-08-20"],
                    "policy_eligible": True,
                }
            ],
            "event_history": [
                {
                    "event_id": "event-old",
                    "title": "Example Bank annual results",
                    "event_type": "earnings_report",
                    "scheduled_at": "2026-03-20",
                    "period": "2025 annual",
                    "lifecycle_status": "VERIFIED",
                    "verification_level": "official",
                    "source": "exchange fixture",
                    "source_rank": 10,
                    "policy_eligible": True,
                    "verified_at": "2026-03-20T18:00:00+08:00",
                }
            ],
        }


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


def test_workspace_exposes_frozen_financial_currentness_and_separates_current_event_lifecycle():
    workspace = DecisionWorkspaceService(_Store()).latest("600000")

    financial = workspace["financial_currentness"]
    assert financial["scope"] == "FROZEN_DECISION"
    assert financial["latest_observed_period"] == "2025-12-31"
    assert financial["expected_report_at"] == "2026-08-20"
    assert financial["latest_period_status"] == "PENDING_EXPECTED_REPORT"
    assert financial["current_confirmation"] == "PENDING"

    events = workspace["corporate_events"]
    assert events["scope"] == "CURRENT_PERSISTED"
    assert events["status"] == "ready"
    assert events["official_source_status"] == "ready"
    assert events["active_events"][0]["lifecycle_status"] == "SCHEDULED"
    assert events["active_events"][0]["verification_level"] == "official"
    assert events["recent_history"][0]["lifecycle_status"] == "VERIFIED"
    assert events["decision_evidence"][0]["scheduled_at"] == "2026-08-20"
    assert events["decision_evidence"][0]["polarity"] == "NEUTRAL_MATERIAL"


def test_workspace_keeps_financial_and_event_sections_explicit_when_legacy_data_is_missing():
    class LegacyStore(_Store):
        def __init__(self):
            super().__init__()
            self._reports[0].pop("atomic_evidence_shadow")

        def cached_market_intelligence(self, key):
            assert key == "corporate_events:600000"
            return None

    workspace = DecisionWorkspaceService(LegacyStore()).latest("600000")

    assert workspace["financial_currentness"] is None
    assert workspace["corporate_events"]["status"] == "unavailable"
    assert workspace["corporate_events"]["active_events"] == []
    assert workspace["corporate_events"]["decision_evidence"] == []


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