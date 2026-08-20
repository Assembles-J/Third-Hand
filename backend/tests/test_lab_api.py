from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.lab.router import create_lab_router
from app.api.v1.route_ownership import owner_for_path
from app.application_services.evaluation.lab_query_service import LabQueryService
from app.domain.evaluation import SampleQualityState, StrategyEvaluation
from app.domain.evaluation.benchmarks import BenchmarkEvaluation, BenchmarkType
from app.domain.experiment import (
    ExperimentDefinition,
    ExperimentStatus,
    ExperimentType,
    ExperimentUniverseMember,
    ExperimentUniverseSnapshot,
)
from app.infrastructure.database.benchmark_evaluation_repository import BenchmarkEvaluationRepository
from app.infrastructure.database.evaluation_outcome_repository import EvaluationOutcomeRepository
from app.infrastructure.database.experiment_repository import ExperimentDefinitionRepository
from app.infrastructure.database.strategy_evaluation_repository import StrategyEvaluationRepository


UTC = timezone.utc
HASH_A = "a" * 64
HASH_B = "b" * 64


class SQLiteStore:
    def __init__(self, path):
        self.path = path

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def _save_experiment(repository, *, version: str, hour: int):
    captured = datetime(2026, 8, 20, hour, 0, tzinfo=UTC)
    snapshot = ExperimentUniverseSnapshot(
        universe_snapshot_id=f"universe-{version}",
        experiment_id="formal-swing-v1-forward",
        experiment_version=version,
        universe_policy_version="candidate-rotation-v1",
        captured_at=captured,
        members=(
            ExperimentUniverseMember(symbol="600519", market="CN"),
            ExperimentUniverseMember(symbol="000001", market="CN"),
        ),
    )
    repository.save_universe(snapshot)
    definition = ExperimentDefinition(
        experiment_id="formal-swing-v1-forward",
        experiment_version=version,
        experiment_type=ExperimentType.FORMAL_OBSERVATION,
        status=ExperimentStatus.ACTIVE,
        strategy_id="SWING_V1",
        strategy_version="1.0.0",
        evidence_schema_version="atomic-evidence-v3",
        universe_policy_version="candidate-rotation-v1",
        universe_snapshot_id=snapshot.universe_snapshot_id,
        universe_snapshot_hash=snapshot.snapshot_hash,
        point_in_time_policy_version="point-in-time-v1",
        action_policy_version="action-policy-v3",
        timeframe_policy_version="timeframe-authority-v1",
        risk_policy_version="risk-v3",
        sizing_policy_version="sizing-v3",
        execution_policy_version="paper-execution-v3",
        outcome_policy_version="1.0.0",
        benchmark_policy_version="1.0.0",
        sample_quality_policy_version="1.0.0",
        evaluation_policy_version="1.0.0",
        started_at=captured,
        created_at=captured,
    )
    repository.save(definition)
    return definition, snapshot


def _strategy_evaluation(definition, snapshot):
    return StrategyEvaluation(
        evaluation_id="eval-v1",
        experiment_id=definition.experiment_id,
        experiment_version=definition.experiment_version,
        universe_snapshot_id=snapshot.universe_snapshot_id,
        universe_snapshot_hash=snapshot.snapshot_hash,
        evaluation_policy_version=definition.evaluation_policy_version,
        sample_quality_policy_version=definition.sample_quality_policy_version,
        outcome_policy_versions=(definition.outcome_policy_version,),
        computed_at=datetime(2026, 8, 20, 6, 0, tzinfo=UTC),
        resolved_decision_count=0,
        decision_outcome_row_count=0,
        nonresolved_decision_outcome_count=0,
        completed_trade_count=0,
        distinct_symbol_count=0,
        sample_quality=SampleQualityState.INSUFFICIENT,
        nonresolved_ratio=Decimal("0"),
        total_return=None,
        max_drawdown=None,
        turnover=None,
        portfolio_metric_reason_codes=("experiment_equity_curve_unavailable_n3_4",),
        max_consecutive_losses=0,
        total_fees=Decimal("0"),
        source_hash=HASH_A,
    )


def _benchmark_evaluation(definition, snapshot):
    return BenchmarkEvaluation(
        benchmark_evaluation_id="benchmark-v1",
        experiment_id=definition.experiment_id,
        experiment_version=definition.experiment_version,
        universe_snapshot_id=snapshot.universe_snapshot_id,
        universe_snapshot_hash=snapshot.snapshot_hash,
        benchmark_policy_id="neutral-diagnostic",
        benchmark_policy_version=definition.benchmark_policy_version,
        benchmark_type=BenchmarkType.NEUTRAL_DIAGNOSTIC,
        computed_at=datetime(2026, 8, 20, 6, 5, tzinfo=UTC),
        resolved_observation_count=0,
        nonresolved_observation_count=0,
        portfolio_benchmark_return=None,
        portfolio_excess_return=None,
        portfolio_metric_reason_codes=("experiment_and_benchmark_equity_curves_unavailable_n3_5",),
        source_hash=HASH_B,
    )


def _client(tmp_path):
    store = SQLiteStore(tmp_path / "lab.db")
    experiments = ExperimentDefinitionRepository(store)
    outcomes = EvaluationOutcomeRepository(store)
    strategy = StrategyEvaluationRepository(store)
    benchmarks = BenchmarkEvaluationRepository(store)
    v1, snapshot_v1 = _save_experiment(experiments, version="1.0.0", hour=3)
    _save_experiment(experiments, version="2.0.0", hour=4)
    strategy.save(_strategy_evaluation(v1, snapshot_v1))
    benchmarks.save_evaluation(_benchmark_evaluation(v1, snapshot_v1))
    service = LabQueryService(experiments, outcomes, strategy, benchmarks)
    app = FastAPI()
    app.include_router(create_lab_router(service))
    return TestClient(app), experiments


def test_lab_api_exposes_stable_read_only_surfaces(tmp_path):
    client, experiments = _client(tmp_path)

    listing = client.get("/v1/lab/experiments")
    assert listing.status_code == 200
    assert listing.json()["count"] == 2
    assert listing.json()["items"][0]["experiment_version"] == "2.0.0"

    latest = client.get("/v1/lab/experiments/formal-swing-v1-forward")
    assert latest.status_code == 200
    assert latest.json()["selection_mode"] == "latest_version"
    assert latest.json()["experiment"]["experiment_version"] == "2.0.0"
    assert latest.json()["universe_member_count"] == 2

    detail = client.get(
        "/v1/lab/experiments/formal-swing-v1-forward",
        params={"version": "1.0.0"},
    )
    assert detail.status_code == 200
    assert detail.json()["selection_mode"] == "explicit_version"
    assert detail.json()["experiment"]["universe_snapshot_hash"] == experiments.get(
        "formal-swing-v1-forward", "1.0.0"
    ).universe_snapshot_hash

    summary = client.get(
        "/v1/lab/experiments/formal-swing-v1-forward/summary",
        params={"version": "1.0.0"},
    )
    assert summary.status_code == 200
    assert summary.json()["strategy"]["available"] is True
    assert summary.json()["benchmark"]["available"] is True
    assert summary.json()["outcome_counts"]["pending_decision_count"] is None
    assert summary.json()["outcome_counts"]["pending_count_reason"] == (
        "pending_outcomes_are_derived_not_materialized_n3_6"
    )

    outcomes = client.get(
        "/v1/lab/experiments/formal-swing-v1-forward/outcomes",
        params={"version": "1.0.0"},
    )
    assert outcomes.status_code == 200
    assert outcomes.json()["terminal_only"] is True
    assert outcomes.json()["pending_materialized"] is False
    assert outcomes.json()["decision_outcomes"] == []

    performance = client.get(
        "/v1/lab/experiments/formal-swing-v1-forward/performance",
        params={"version": "1.0.0"},
    )
    assert performance.status_code == 200
    assert performance.json()["strategy"]["sample_quality"] == "INSUFFICIENT"
    assert performance.json()["strategy"]["total_return"] is None
    assert performance.json()["benchmark"]["portfolio_excess_return"] is None

    breakdown = client.get(
        "/v1/lab/experiments/formal-swing-v1-forward/breakdown",
        params={"version": "1.0.0"},
    )
    assert breakdown.status_code == 200
    assert breakdown.json()["action_breakdown"] == []
    assert breakdown.json()["benchmark_horizon_breakdown"] == []

    comparison = client.get(
        "/v1/lab/compare",
        params=[
            ("ids", "formal-swing-v1-forward@1.0.0"),
            ("ids", "formal-swing-v1-forward@2.0.0"),
        ],
    )
    assert comparison.status_code == 200
    assert len(comparison.json()["rows"]) == 2
    assert comparison.json()["rows"][0]["strategy_available"] is True
    assert comparison.json()["rows"][1]["strategy_available"] is False

    assert client.get("/v1/lab/calibration").status_code == 404
    assert owner_for_path("/v1/lab/experiments") == "lab"


def test_lab_api_filters_and_errors_are_explicit(tmp_path):
    client, _ = _client(tmp_path)

    filtered = client.get(
        "/v1/lab/experiments",
        params={"strategy_id": "SWING_V1", "experiment_type": "FORMAL_OBSERVATION"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 2

    missing = client.get("/v1/lab/experiments/does-not-exist")
    assert missing.status_code == 404

    one_selector = client.get("/v1/lab/compare", params=[("ids", "formal-swing-v1-forward@1.0.0")])
    assert one_selector.status_code == 422
