from types import SimpleNamespace

from app.model_policy import ModelPolicy


def test_default_atomic_evidence_uses_flash_without_thinking():
    selected = ModelPolicy().select(
        SimpleNamespace(conflicts=(), facts=()), default_model="flash", reasoning_model="pro", default_max_tokens=900
    )

    assert selected.tier == "FLASH_DEFAULT"
    assert selected.model == "flash"
    assert selected.thinking is False


def test_high_severity_conflict_escalates_to_reasoning_model():
    selected = ModelPolicy().select(
        SimpleNamespace(conflicts=(SimpleNamespace(severity="high"),), facts=()),
        default_model="flash", reasoning_model="pro", default_max_tokens=900,
    )

    assert selected.tier == "PRO_ESCALATION"
    assert selected.model == "pro"
    assert selected.thinking is True
    assert selected.escalation_reasons == ("high_severity_evidence_conflict",)
