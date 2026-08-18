from types import SimpleNamespace

from app.decision_models import ActionCandidate
from app.decision_semantics import DecisionArbiter, execution_side, formal_action_from_report


def _candidate(action):
    return ActionCandidate(action=action, priority=30, policy_score=.3, triggered_rule_ids=(f"candidate.{action.lower()}",))


def test_entry_semantics_map_open_to_buy_and_watch_to_wait():
    arbiter = DecisionArbiter()
    flat = SimpleNamespace(position=None)

    assert arbiter.arbitrate(flat, (_candidate("OPEN"),)).action == "BUY"
    wait = arbiter.arbitrate(flat, (_candidate("WATCH"),))
    assert wait.action == "WAIT"
    assert "legacy_candidate:WATCH" in wait.reason_codes


def test_position_watch_becomes_hold_not_reduce():
    arbiter = DecisionArbiter()
    held = SimpleNamespace(position=object())

    decision = arbiter.arbitrate(held, (_candidate("WATCH"),))

    assert decision.action == "HOLD"
    assert "legacy_candidate:WATCH" in decision.reason_codes
    assert "position.no_reduce_without_position_risk_rule" in decision.reason_codes


def test_position_management_actions_keep_their_explicit_meaning():
    arbiter = DecisionArbiter()
    held = SimpleNamespace(position=object())

    assert arbiter.arbitrate(held, (_candidate("ADD"),)).action == "ADD"
    assert arbiter.arbitrate(held, (_candidate("REDUCE"),)).action == "REDUCE"
    assert arbiter.arbitrate(held, (_candidate("EXIT"),)).action == "EXIT"


def test_formal_action_reader_prefers_new_semantics_and_can_replay_legacy_reports():
    assert formal_action_from_report({"action": "OPEN", "formal_action": "WAIT"}) == "WAIT"
    assert formal_action_from_report({"action": "OPEN"}) == "BUY"
    assert execution_side("BUY") == "BUY"
    assert execution_side("WAIT") is None
