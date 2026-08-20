from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.experiment import ExperimentDefinition, ExperimentStatus, ExperimentType
from app.infrastructure.database.experiment_repository import ExperimentDefinitionRepository
from app.storage import PortfolioStore


def _formal(**overrides):
    payload = {
        "experiment_id": "formal-swing-v1-forward",
        "experiment_version": "1.0.0",
        "experiment_type": ExperimentType.FORMAL_OBSERVATION,
        "status": ExperimentStatus.ACTIVE,
        "strategy_id": "SWING_V1",
        "strategy_version": "1.0.0",
        "evidence_schema_version": "atomic-evidence-v3",
        "universe_policy_version": "candidate-rotation-v1",
        "point_in_time_policy_version": "point-in-time-v1",
        "action_policy_version": "action-policy-v3",
        "timeframe_policy_version": "timeframe-authority-v1",
        "risk_policy_version": "risk-v3",
        "sizing_policy_version": "sizing-v3",
        "execution_policy_version": "paper-execution-v3",
        "outcome_policy_version": "outcome-v1",
        "benchmark_policy_version": "benchmark-v1",
        "sample_quality_policy_version": "sample-quality-v1",
        "evaluation_policy_version": "evaluation-v1",
        "started_at": datetime(2026, 8, 20, 3, 0, tzinfo=timezone.utc),
        "created_at": datetime(2026, 8, 20, 3, 0, tzinfo=timezone.utc),
    }
    payload.update(overrides)
    return ExperimentDefinition(**payload)


def test_formal_experiment_is_frozen_and_hash_is_deterministic():
    first = _formal()
    second = _formal()

    assert first.canonical_json() == second.canonical_json()
    assert first.definition_hash == second.definition_hash
    assert first.canonical_payload()["experiment_type"] == "FORMAL_OBSERVATION"

    with pytest.raises(ValidationError):
        first.strategy_version = "2.0.0"


def test_formal_experiment_requires_policy_lineage_and_rejects_ai_fields():
    with pytest.raises(ValidationError):
        _formal(action_policy_version=None)

    with pytest.raises(ValidationError):
        _formal(agent_id="ai-swing")

    with pytest.raises(ValidationError):
        _formal(started_at=datetime(2026, 8, 20, 3, 0))


def test_repository_round_trip_is_append_only_and_idempotent(tmp_path):
    repository = ExperimentDefinitionRepository(PortfolioStore(tmp_path / "experiments.db"))
    definition = _formal()

    saved = repository.save(definition)
    loaded = repository.get(definition.experiment_id, definition.experiment_version)
    saved_again = repository.save(definition)

    assert saved.definition_hash == definition.definition_hash
    assert saved_again == definition
    assert loaded == definition
    assert repository.list_for_strategy("SWING_V1") == (definition,)

    conflicting = _formal(strategy_version="1.0.1")
    with pytest.raises(ValueError, match="immutable"):
        repository.save(conflicting)
