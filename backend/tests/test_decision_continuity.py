from datetime import datetime, timezone
from types import SimpleNamespace

from app.decision_continuity import DecisionContinuityPolicy


def _context(*, input_hash: str = "same-input", gates=(), **overrides):
    context = SimpleNamespace(
        symbol="600519",
        position=None,
        input_hash=input_hash,
        generated_at=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
        data_quality=SimpleNamespace(model_dump=lambda mode: {"action_gates": list(gates)}),
    )
    for name, value in overrides.items():
        setattr(context, name, value)
    return context


def _prior(*, action: str = "WAIT", input_hash: str = "same-input", gates=(), fingerprint=None):
    memory = {"episode_id": "episode-existing"}
    if fingerprint is not None:
        memory["material_fingerprint"] = fingerprint
    return {
        "decision_id": "prior-1",
        "formal_action": action,
        "input_hash": input_hash,
        "data_quality": {"action_gates": list(gates)},
        "decision_memory": memory,
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


def test_quote_refresh_changes_audit_hash_but_cannot_flip_formal_action():
    policy = DecisionContinuityPolicy()
    previous = _context(quote=SimpleNamespace(price=10.50, as_of="2026-08-18T10:00:00+00:00"))
    prior = _prior(fingerprint=policy._material_fingerprint(previous))
    current = _context(
        input_hash="new-input",
        quote=SimpleNamespace(price=10.48, as_of="2026-08-18T14:00:00+00:00"),
    )
    action, memory = policy.assess(current, "BUY", prior)

    assert action == "WAIT"
    assert memory.input_changed is True
    assert memory.material_change is False
    assert memory.material_change_reason == "continuity_preserved_prior_action"
    assert memory.material_change_components == ()


def test_strategic_state_change_allows_a_new_formal_action():
    policy = DecisionContinuityPolicy()
    previous = _context(risk=SimpleNamespace(risk_level="low"))
    prior = _prior(fingerprint=policy._material_fingerprint(previous))
    current = _context(input_hash="new-input", risk=SimpleNamespace(risk_level="high"))

    action, memory = policy.assess(current, "BUY", prior)

    assert action == "BUY"
    assert memory.material_change is True
    assert memory.material_change_reason == "material_fingerprint_changed"
    assert memory.material_change_components == ("risk_level",)


def test_position_age_is_derived_from_the_frozen_open_timestamp():
    context = _context()
    context.position = SimpleNamespace(opened_at="2026-08-15T10:00:00+00:00")
    action, memory = DecisionContinuityPolicy().assess(context, "HOLD", None)

    assert action == "HOLD"
    assert memory.position_age == 3
