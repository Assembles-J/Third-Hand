from uuid import uuid4

import pytest

from app.storage import PortfolioStore


def _frozen_report(decision_id: str = "decision-1") -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "context_id": "context-1",
        "symbol": "600519",
        "input_hash": "frozen-input-hash",
        "generated_at": "2026-08-18T10:00:00+08:00",
        "policy_version": "swing-policy-v3-position-action-semantics",
        "evidence": [],
        "action_candidates": [],
        "operation_items": [],
    }


def test_feedback_event_links_actual_and_hypothetical_outcomes_to_frozen_decision(tmp_path):
    store = PortfolioStore(tmp_path / "feedback.db")
    store.save_decision_report(_frozen_report())
    store.save_paper_account(10_000)
    execution = store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="test", side="BUY", quantity=100,
        price=10, decision_id="decision-1", reason="feedback fixture",
    )

    event = store.record_feedback_event({
        "decision_id": "decision-1",
        "execution_log_id": execution["id"],
        "user_action": "accepted",
        "actual_outcome": {"window": "5d", "return_percent": 3.2},
        "hypothetical_outcome": {"action": "WAIT", "return_percent": 0.0},
        "explicit_feedback": "execution matched plan",
        "review_label": "reviewed",
    })

    assert event["decision_input_hash"] == "frozen-input-hash"
    assert event["quantity"] == 100
    assert event["actual_outcome"]["return_percent"] == 3.2
    assert event["hypothetical_outcome"]["action"] == "WAIT"
    assert event["automatic_tuning"] is False
    assert store.feedback_events("decision-1")[0]["feedback_id"] == event["feedback_id"]
    dataset = store.feedback_evaluation_dataset(event["policy_version"])
    assert dataset[0]["decision_input_hash"] == "frozen-input-hash"
    assert dataset[0]["automatic_tuning"] is False


def test_feedback_rejects_unknown_decision_or_execution_from_another_decision(tmp_path):
    store = PortfolioStore(tmp_path / "feedback-errors.db")
    with pytest.raises(ValueError, match="feedback_frozen_decision_not_found"):
        store.record_feedback_event({"decision_id": "missing", "user_action": "accepted"})

    store.save_decision_report(_frozen_report("decision-1"))
    store.save_decision_report(_frozen_report("decision-2"))
    store.save_paper_account(10_000)
    execution = store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="test", side="BUY", quantity=100,
        price=10, decision_id="decision-1", reason="mismatch fixture",
    )
    with pytest.raises(ValueError, match="feedback_execution_decision_mismatch"):
        store.record_feedback_event({
            "decision_id": "decision-2", "execution_log_id": execution["id"],
            "user_action": "accepted",
        })
