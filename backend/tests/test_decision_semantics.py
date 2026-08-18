from types import SimpleNamespace

from app.decision_models import ActionCandidate
from app.decision_semantics import DecisionArbiter, execution_side, formal_action_from_report


def _candidate(action):
    return ActionCandidate(action=action, priority=30, policy_score=.3, triggered_rule_ids=(f"candidate.{action.lower()}",))


def test_entry_semantics_map_open_to_buy_and_watch_to_wait():
    arbiter = DecisionArbiter()
    flat = SimpleNamespace(position=None)

    buy = arbiter.arbitrate(flat, (_candidate("OPEN"),))
    assert buy.action == "BUY"
    assert buy.next_state == "ENTRY_PENDING"
    wait = arbiter.arbitrate(flat, (_candidate("WATCH"),))
    assert wait.action == "WAIT"
    assert wait.next_state == "FLAT"
    assert "legacy_candidate:WATCH" in wait.reason_codes


def test_position_watch_becomes_hold_not_reduce():
    arbiter = DecisionArbiter()
    held = SimpleNamespace(position=object())

    decision = arbiter.arbitrate(held, (_candidate("WATCH"),))

    assert decision.action == "HOLD"
    assert decision.prior_state == "HOLDING"
    assert decision.next_state == "HOLDING"
    assert "legacy_candidate:WATCH" in decision.reason_codes
    assert "position.no_reduce_without_position_risk_rule" in decision.reason_codes


def test_position_management_actions_keep_their_explicit_meaning():
    arbiter = DecisionArbiter()
    held = SimpleNamespace(position=object())

    assert arbiter.arbitrate(held, (_candidate("ADD"),)).action == "ADD"
    assert arbiter.arbitrate(held, (_candidate("REDUCE"),)).action == "REDUCE"
    assert arbiter.arbitrate(held, (_candidate("EXIT"),)).action == "EXIT"
    assert arbiter.arbitrate(held, (_candidate("REDUCE"),)).next_state == "REDUCE_PENDING"
    assert arbiter.arbitrate(held, (_candidate("EXIT"),)).next_state == "EXIT_PENDING"


def test_blocked_entry_exposes_the_existing_event_gate_reason_code():
    gate = SimpleNamespace(action="OPEN", permission="blocked", reasons=("event_risk.upcoming_earnings:near",))
    flat = SimpleNamespace(position=None, data_quality=SimpleNamespace(action_gates=(gate,)))

    decision = DecisionArbiter().arbitrate(flat, (_candidate("WATCH"),))

    assert decision.action == "WAIT"
    assert "event_risk.upcoming_earnings:near" in decision.reason_codes


def test_formal_action_reader_prefers_new_semantics_and_can_replay_legacy_reports():
    assert formal_action_from_report({"action": "OPEN", "formal_action": "WAIT"}) == "WAIT"
    assert formal_action_from_report({"action": "OPEN"}) == "BUY"
    assert execution_side("BUY") == "BUY"
    assert execution_side("WAIT") is None
