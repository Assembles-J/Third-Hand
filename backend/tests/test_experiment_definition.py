from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.experiment import (
    ExperimentDefinition,
    ExperimentStatus,
    ExperimentType,
    ExperimentUniverseSnapshot,
    ExperimentUniverseSourceKind,
)
from app.infrastructure.database.experiment_repository import ExperimentDefinitionRepository
from app.storage import PortfolioStore


def _universe(**overrides):
    payload = {
        "universe_snapshot_id": "formal-swing-v1-forward:1.0.0:universe",
        "experiment_id": "formal-swing-v1-forward",
        "experiment_version": "1.0.0",
        "universe_policy_version": "explicit-forward-universe-v1",
        "captured_at": datetime(2026, 8, 20, 3, 0, tzinfo=timezone.utc),
        # Deliberately out of order; the contract canonicalizes membership.
        "members": (
            {"symbol": "01810", "market": "HK"},
            {"symbol": "600519", "market": "CN_A"},
        ),
        "source_kind": ExperimentUniverseSourceKind.EXPLICIT,
    }
    payload.update(overrides)
    return ExperimentUniverseSnapshot(**payload)


def _formal(**overrides):
    universe = overrides.pop("universe", None) or _universe()
    payload = {
        "experiment_id": "formal-swing-v1-forward",
        "experiment_version": "1.0.0",
        "experiment_type": ExperimentType.FORMAL_OBSERVATION,
        "status": ExperimentStatus.ACTIVE,
        "strategy_id": "SWING_V1",
        "strategy_version": "1.0.0",
        "evidence_schema_version": "atomic-evidence-v3",
        "universe_policy_version": universe.universe_policy_version,
        "universe_snapshot_id": universe.universe_snapshot_id,
        "universe_snapshot_hash": universe.snapshot_hash,
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


def test_universe_snapshot_is_canonical_frozen_and_hash_stable():
    first = _universe()
    second = _universe(
        members=(
            {"symbol": "600519", "market": "CN"},
            {"symbol": "01810", "market": "HK"},
        )
    )

    assert first.members == second.members
    assert [(item.market, item.symbol) for item in first.members] == [
        ("CN", "600519"),
        ("HK", "01810"),
    ]
    assert first.snapshot_hash == second.snapshot_hash
    assert first.contains("600519", "CN_A")
    assert not first.contains("AAPL", "US")

    with pytest.raises(ValidationError):
        _universe(members=({"symbol": "600519", "market": "CN"},) * 2)

    with pytest.raises(ValidationError):
        first.members = ()


def test_formal_experiment_is_frozen_and_hash_is_deterministic():
    first = _formal()
    second = _formal()

    assert first.canonical_json() == second.canonical_json()
    assert first.definition_hash == second.definition_hash
    assert first.canonical_payload()["experiment_type"] == "FORMAL_OBSERVATION"
    assert first.universe_snapshot_hash == _universe().snapshot_hash

    with pytest.raises(ValidationError):
        first.strategy_version = "2.0.0"


def test_formal_experiment_requires_policy_lineage_universe_hash_and_rejects_ai_fields():
    with pytest.raises(ValidationError):
        _formal(action_policy_version=None)

    with pytest.raises(ValidationError):
        _formal(agent_id="ai-swing")

    with pytest.raises(ValidationError):
        _formal(started_at=datetime(2026, 8, 20, 3, 0))

    with pytest.raises(ValidationError):
        _formal(universe_snapshot_hash="not-a-sha256")


def test_repository_requires_matching_persisted_universe_and_is_append_only(tmp_path):
    repository = ExperimentDefinitionRepository(PortfolioStore(tmp_path / "experiments.db"))
    universe = _universe()
    definition = _formal(universe=universe)

    with pytest.raises(ValueError, match="persisted universe"):
        repository.save(definition)

    saved_universe = repository.save_universe(universe)
    saved = repository.save(definition)
    loaded = repository.get(definition.experiment_id, definition.experiment_version)
    loaded_universe = repository.get_universe_for_experiment(
        definition.experiment_id,
        definition.experiment_version,
    )
    saved_again = repository.save(definition)

    assert saved_universe.snapshot_hash == universe.snapshot_hash
    assert loaded_universe == universe
    assert saved.definition_hash == definition.definition_hash
    assert saved_again == definition
    assert loaded == definition
    assert repository.list_for_strategy("SWING_V1") == (definition,)

    changed_membership = _universe(
        members=(
            {"symbol": "600519", "market": "CN"},
            {"symbol": "000001", "market": "CN"},
        )
    )
    with pytest.raises(ValueError, match="immutable"):
        repository.save_universe(changed_membership)

    conflicting = _formal(universe=universe, strategy_version="1.0.1")
    with pytest.raises(ValueError, match="immutable"):
        repository.save(conflicting)


def test_repository_rejects_definition_universe_hash_or_policy_mismatch(tmp_path):
    repository = ExperimentDefinitionRepository(PortfolioStore(tmp_path / "experiments.db"))
    universe = _universe()
    repository.save_universe(universe)

    with pytest.raises(ValueError, match="hash"):
        repository.save(_formal(universe=universe, universe_snapshot_hash="0" * 64))

    with pytest.raises(ValueError, match="policy"):
        repository.save(
            _formal(
                universe=universe,
                universe_policy_version="another-universe-policy-v1",
            )
        )
