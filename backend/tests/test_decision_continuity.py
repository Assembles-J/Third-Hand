from datetime import datetime, timezone
from types import SimpleNamespace

from app.decision_continuity import DecisionContinuityPolicy


def _context(*, input_hash: str = "same-input", gates=()):
    return SimpleNamespace(
        symbol="600519",
        position=None,
        input_hash=input_hash,
        generated_at=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
        data_quality=SimpleNamespace(model_dump=lambda mode: {"action_gates": list(gates)}),
    )


def _prior(*, action: str = "WAIT", input_hash: str = "same-input", gates=()):
    return {
        "decision_id": "prior-1",
        "formal_action": action,
        "input_hash": input_hash,
        "data_quality": {"action_gates": list(gates)},
        "decision_memory": {"episode_id": "episode-existing"},
        "entry_decision": {"prior_state": "FLAT"},
    }


def test_same_inputs_cannot_flip_formal_action_without_material_change():
    action, memory = DecisionContinuityPolicy().assess(_context(), "BUY", _prior())

    assert action == "WAIT"
    assert memory.prior_decision_id == "prior-1"
    assert memory.episode_id == "episode-existing"
    assert memory.material_change is False
    assert memory.material_change_reason == "continuity_preserved_prior_action"


def test_hard_gate_change_allows_new_action_and_opens_new_episode():
    previous_gates = ({"action": "OPEN", "permission": "blocked"},)
    current_gates = ({"action": "OPEN", "permission": "allowed"},)
    action, memory = DecisionContinuityPolicy().assess(
        _context(gates=current_gates), "BUY", _prior(gates=previous_gates)
    )

    assert action == "BUY"
    assert memory.material_change is True
    assert memory.material_change_reason == "hard_gate_changed"
    assert memory.episode_id != "episode-existing"


def test_changed_input_is_a_material_change():
    action, memory = DecisionContinuityPolicy().assess(_context(input_hash="new-input"), "BUY", _prior())

    assert action == "BUY"
    assert memory.material_change is True
    assert memory.material_change_reason == "decision_input_changed"
