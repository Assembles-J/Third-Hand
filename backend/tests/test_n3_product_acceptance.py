from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
import sqlite3
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.lab.router import create_lab_router
from app.application_services.evaluation import (
    BenchmarkEvaluationService,
    OutcomeResolver,
    StrategyEvaluationService,
)
from app.application_services.evaluation.lab_query_service import LabQueryService
from app.domain.evaluation import (
    BenchmarkConstituentSource,
    BenchmarkPolicy,
    BenchmarkType,
    EvaluationPolicy,
    ExecutionDisposition,
    OutcomeStatus,
    SampleQualityPolicy,
    SampleQualityState,
)
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


TZ = ZoneInfo("Asia/Shanghai")
SESSIONS = (
    "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
    "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15",
    "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22",
    "2026-01-23", "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29",
    "2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05",
    "2026-02-06",
)


class SQLiteStore:
    def __init__(self, path):
        self.path = path

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


class AcceptanceCalendar:
    def latest_session_date(self, market, moment):
        eligible = [item for item in SESSIONS if item <= moment.date().isoformat()]
        return eligible[-1] if eligible else None

    def latest_completed_session_date(self, market, moment):
        day = moment.date().isoformat()
        eligible = [item for item in SESSIONS if item < day]
        if day in SESSIONS and moment.timetz().replace(tzinfo=None) >= time(15, 0):
            eligible.append(day)
        return eligible[-1] if eligible else None

    def session_dates(self, market, start, end):
        return [item for item in SESSIONS if start <= item <= end]

    def session_close(self, market, session_date):
        day = datetime.fromisoformat(session_date).date()
        return datetime.combine(day, time(15, 0), tzinfo=TZ)


class AcceptanceSource:
    def __init__(self):
        self.bundles = {}
        self.rows = {}
        self.fills = []
        self.deferrals = {}
        self.episodes = {}
        self.episode_fills = []
        self.extra_reports = {}

    def decision_bundle(self, decision_id):
        return self.bundles.get(decision_id)

    def decision_report(self, decision_id):
        bundle = self.bundles.get(decision_id)
        return bundle["report"] if bundle is not None else self.extra_reports.get(decision_id)

    def daily_bars_between(self, symbol, start, end):
        return tuple(
            row for row in self.rows.get(symbol, ())
            if start <= row["trading_date"] <= end
        )

    def fills_for_decision(self, decision_id):
        return tuple(item for item in self.fills if item.get("decision_id") == decision_id)

    def deferral_for_decision(self, decision_id):
        return self.deferrals.get(decision_id)

    def position_episode(self, episode_id):
        return self.episodes.get(episode_id)

    def fills_for_episode(self, symbol, opened_at, closed_at):
        return tuple(self.episode_fills)


def bar(day, close, *, high=None, low=None):
    close = Decimal(str(close))
    return {
        "trading_date": day,
        "open": str(close),
        "close": str(close),
        "high": str(high if high is not None else close),
        "low": str(low if low is not None else close),
        "adjustment": "qfq",
        "source": "n3-acceptance-fixture",
        "updated_at": f"{day}T16:00:00+08:00",
    }


def decision_bundle(decision_id, *, symbol, action, at, price):
    return {
        "report": {
            "decision_id": decision_id,
            "context_id": f"context-{decision_id}",
            "symbol": symbol,
            "generated_at": at,
            "formal_action": action,
            "input_hash": f"frozen-{decision_id}",
            "market_price": str(price) if price is not None else None,
            "sizing": {
                "status": "ready",
                "execution_disposition": "ready",
                "suggested_quantity": 10,
                "max_executable_quantity": 10,
                "blocked_reasons": [],
            },
        },
        "context": {
            "symbol": symbol,
            "quote": {"price": str(price)} if price is not None else None,
            "instrument": {"market": "CN"},
            "market_regime": {"regime": "range"},
        },
    }


def build_experiment(repository):
    captured = datetime(2026, 1, 5, 9, 0, tzinfo=TZ)
    universe = ExperimentUniverseSnapshot(
        universe_snapshot_id="formal-swing-v1-acceptance:1.0.0:universe",
        experiment_id="formal-swing-v1-acceptance",
        experiment_version="1.0.0",
        universe_policy_version="acceptance-universe-v1",
        captured_at=captured,
        members=(
            ExperimentUniverseMember(symbol="600519", market="CN"),
            ExperimentUniverseMember(symbol="000001", market="CN"),
        ),
    )
    repository.save_universe(universe)
    experiment = ExperimentDefinition(
        experiment_id="formal-swing-v1-acceptance",
        experiment_version="1.0.0",
        experiment_type=ExperimentType.FORMAL_OBSERVATION,
        status=ExperimentStatus.ACTIVE,
        strategy_id="SWING_V1",
        strategy_version="1.0.0",
        evidence_schema_version="atomic-evidence-v3",
        universe_policy_version=universe.universe_policy_version,
        universe_snapshot_id=universe.universe_snapshot_id,
        universe_snapshot_hash=universe.snapshot_hash,
        point_in_time_policy_version="point-in-time-v1",
        action_policy_version="action-policy-v3",
        timeframe_policy_version="timeframe-authority-v1",
        risk_policy_version="risk-v3",
        sizing_policy_version="sizing-v3",
        execution_policy_version="paper-execution-v3",
        outcome_policy_version="1.0.0",
        benchmark_policy_version="acceptance-benchmark-v1",
        sample_quality_policy_version="acceptance-sample-v1",
        evaluation_policy_version="acceptance-eval-v1",
        started_at=captured,
        created_at=captured,
    )
    repository.save(experiment)
    return experiment, universe


def evaluation_policy():
    return EvaluationPolicy(
        policy_id="n3-acceptance-evaluation",
        version="acceptance-eval-v1",
        decision_count_rule="unique_decision_with_any_resolved_horizon_v1",
        action_breakdown_rule="action_and_horizon_resolved_rows_v1",
        regime_breakdown_rule="regime_and_horizon_resolved_rows_v1",
        episode_metric_rule="closed_episode_net_return_and_realized_pnl_v1",
        portfolio_return_rule="require_experiment_equity_curve_no_episode_compound_proxy_v1",
        nonresolved_ratio_rule="terminal_decision_outcome_rows_v1",
    )


def sample_policy():
    return SampleQualityPolicy(
        policy_id="n3-acceptance-sample-quality",
        version="acceptance-sample-v1",
        low_min_resolved_decisions=1,
        low_min_distinct_symbols=1,
        usable_min_resolved_decisions=2,
        usable_min_completed_episodes=2,
        usable_min_distinct_symbols=1,
        usable_max_nonresolved_ratio=Decimal("0.8"),
        strong_min_resolved_decisions=4,
        strong_min_completed_episodes=4,
        strong_min_distinct_symbols=2,
        strong_max_nonresolved_ratio=Decimal("0.2"),
    )


def benchmark_policy():
    return BenchmarkPolicy(
        benchmark_policy_id="n3-acceptance-equal-weight",
        version="acceptance-benchmark-v1",
        benchmark_type=BenchmarkType.EQUAL_WEIGHT_ELIGIBLE_UNIVERSE,
        constituent_source=BenchmarkConstituentSource.EXPERIMENT_UNIVERSE,
    )


def test_formal_swing_v1_full_n3_chain_is_point_in_time_and_universe_safe(tmp_path):
    store = SQLiteStore(tmp_path / "n3.db")
    experiments = ExperimentDefinitionRepository(store)
    outcomes = EvaluationOutcomeRepository(store)
    strategies = StrategyEvaluationRepository(store)
    benchmarks = BenchmarkEvaluationRepository(store)
    experiment, universe = build_experiment(experiments)

    source = AcceptanceSource()
    source.bundles = {
        "d1": decision_bundle(
            "d1", symbol="600519", action="BUY",
            at=datetime(2026, 1, 5, 10, 0, tzinfo=TZ), price=Decimal("100"),
        ),
        "d2": decision_bundle(
            "d2", symbol="000001", action="WAIT",
            at=datetime(2026, 1, 5, 10, 5, tzinfo=TZ), price=None,
        ),
        "d3": decision_bundle(
            "d3", symbol="600519", action="BUY",
            at=datetime(2026, 1, 8, 14, 0, tzinfo=TZ), price=Decimal("106"),
        ),
    }
    source.rows = {
        "600519": [
            bar("2026-01-02", 100),
            # Must never leak into a 10:00 decision's forward window.
            bar("2026-01-05", 999, high=1200, low=1),
            bar("2026-01-06", 102, high=103, low=99),
            bar("2026-01-07", 104, high=105, low=101),
            bar("2026-01-08", 106, high=108, low=100),
        ],
        "000001": [bar("2026-01-02", 20), bar("2026-01-08", 21)],
        # Current/mutable attention symbol outside the frozen experiment.
        "01810": [bar("2026-01-02", 30), bar("2026-01-08", 90)],
    }
    source.fills = [{
        "id": "fill-buy-d1", "decision_id": "d1", "side": "BUY", "quantity": 10,
        "price": 100, "fee": 1,
        "execution_quote_at": "2026-01-05T10:01:00+08:00",
        "fill_price_mode": "NEXT_ELIGIBLE_OBSERVED_QUOTE",
        "executed_at": "2026-01-05T10:01:00+08:00",
    }]
    source.episodes["ep1"] = {
        "episode_id": "ep1", "symbol": "600519", "entry_price": 100,
        "opened_at": "2026-01-05T10:01:00+08:00",
        "closed_at": "2026-01-08T14:00:00+08:00",
    }
    source.episode_fills = [
        source.fills[0],
        {
            "id": "fill-exit-ep1", "decision_id": "exit-d1", "side": "SELL",
            "quantity": 10, "price": 106, "fee": 1,
            "execution_quote_at": "2026-01-08T14:00:00+08:00",
            "fill_price_mode": "NEXT_ELIGIBLE_OBSERVED_QUOTE",
            "executed_at": "2026-01-08T14:00:00+08:00",
        },
    ]
    source.extra_reports["exit-d1"] = {"formal_action": "EXIT"}

    resolver = OutcomeResolver(
        source,
        outcome_repository=outcomes,
        experiment_repository=experiments,
        trading_calendar=AcceptanceCalendar(),
    )
    d1 = resolver.resolve_decision(
        experiment, "d1", as_of=datetime(2026, 1, 8, 16, 0, tzinfo=TZ)
    )
    h3 = next(row for row in d1.decision_outcomes if row.horizon_sessions == 3)
    assert h3.outcome_status == OutcomeStatus.RESOLVED
    assert h3.observation_end.isoformat() == "2026-01-08T15:00:00+08:00"
    assert h3.forward_return == Decimal("0.06")
    assert h3.mfe == Decimal("0.08")
    assert h3.mae == Decimal("-0.01")
    assert d1.execution_outcome.execution_disposition == ExecutionDisposition.EXECUTED

    d2 = resolver.resolve_decision(
        experiment, "d2", as_of=datetime(2026, 1, 8, 16, 0, tzinfo=TZ)
    )
    assert all(row.outcome_status == OutcomeStatus.INSUFFICIENT_DATA for row in d2.decision_outcomes)
    assert {row.outcome_reason_codes for row in d2.decision_outcomes} == {
        ("reference_price_unavailable",),
    }

    d3 = resolver.resolve_decision(
        experiment, "d3", as_of=datetime(2026, 1, 8, 14, 30, tzinfo=TZ)
    )
    assert all(row.outcome_status == OutcomeStatus.PENDING for row in d3.decision_outcomes)
    assert not any(row.decision_id == "d3" for row in outcomes.list_decisions(
        experiment.experiment_id, experiment.experiment_version
    ))

    episode = resolver.resolve_episode(
        experiment, "ep1", as_of=datetime(2026, 1, 8, 16, 0, tzinfo=TZ)
    )
    assert episode.outcome_status == OutcomeStatus.RESOLVED
    assert episode.net_return == Decimal("0.058")
    assert episode.realized_pnl == Decimal("58")
    assert episode.fees == Decimal("2")
    assert episode.slippage == Decimal("0")

    evaluation = StrategyEvaluationService(
        outcomes,
        evaluation_repository=strategies,
        experiment_repository=experiments,
        evaluation_policy=evaluation_policy(),
        sample_quality_policy=sample_policy(),
    ).evaluate(experiment, computed_at=datetime(2026, 1, 9, 12, 0, tzinfo=TZ))
    assert evaluation.universe_snapshot_hash == universe.snapshot_hash
    assert evaluation.resolved_decision_count == 1
    assert evaluation.completed_trade_count == 1
    assert evaluation.sample_quality == SampleQualityState.LOW
    assert evaluation.win_rate == Decimal("1")
    assert evaluation.total_fees == Decimal("2")
    assert evaluation.total_return is None and evaluation.max_drawdown is None
    assert evaluation.portfolio_metric_reason_codes == (
        "experiment_equity_curve_unavailable_n3_4",
    )
    assert [(row.action, row.horizon_sessions) for row in evaluation.action_breakdown] == [
        ("BUY", 3),
    ]
    assert [(row.market_regime, row.horizon_sessions) for row in evaluation.regime_breakdown] == [
        ("range", 3),
    ]

    benchmark = BenchmarkEvaluationService(
        outcomes,
        source,
        experiment_repository=experiments,
        benchmark_repository=benchmarks,
        trading_calendar=AcceptanceCalendar(),
    ).evaluate(
        experiment,
        benchmark_policy(),
        computed_at=datetime(2026, 1, 9, 12, 5, tzinfo=TZ),
    )
    assert benchmark.resolved_observation_count == 1
    assert benchmark.mean_strategy_forward_return == Decimal("0.06")
    assert benchmark.mean_benchmark_forward_return == Decimal("0.055")
    assert benchmark.mean_excess_forward_return == Decimal("0.005")
    assert benchmark.portfolio_benchmark_return is None
    assert benchmark.portfolio_excess_return is None
    observation = benchmarks.list_observations(
        experiment.experiment_id,
        experiment.experiment_version,
        experiment.benchmark_policy_version,
    )[0]
    assert observation.reference_session == "2026-01-02"
    assert observation.end_session == "2026-01-08"
    assert observation.constituent_count == 2
    assert observation.universe_snapshot_hash == universe.snapshot_hash

    changed = universe.model_copy(update={
        "members": (
            ExperimentUniverseMember(symbol="600519", market="CN"),
            ExperimentUniverseMember(symbol="000001", market="CN"),
            ExperimentUniverseMember(symbol="01810", market="HK"),
        )
    })
    with pytest.raises(ValueError, match="immutable"):
        experiments.save_universe(changed)

    app = FastAPI()
    app.include_router(create_lab_router(LabQueryService(experiments, outcomes, strategies, benchmarks)))
    client = TestClient(app)
    base = f"/v1/lab/experiments/{experiment.experiment_id}"

    detail = client.get(base)
    assert detail.status_code == 200
    assert detail.json()["experiment"]["universe_snapshot_hash"] == universe.snapshot_hash
    assert detail.json()["universe_member_count"] == 2

    summary = client.get(f"{base}/summary")
    assert summary.status_code == 200
    assert summary.json()["strategy"]["sample_quality"] == "LOW"
    assert summary.json()["benchmark"]["benchmark_type"] == "EQUAL_WEIGHT_ELIGIBLE_UNIVERSE"
    assert summary.json()["outcome_counts"]["decision_resolved_count"] == 1
    assert summary.json()["outcome_counts"]["decision_insufficient_count"] == 4
    assert summary.json()["outcome_counts"]["pending_decision_count"] is None
    assert summary.json()["outcome_counts"]["pending_count_reason"] == (
        "pending_outcomes_are_derived_not_materialized_n3_6"
    )

    terminal = client.get(f"{base}/outcomes")
    assert terminal.status_code == 200
    assert terminal.json()["terminal_only"] is True
    assert terminal.json()["pending_materialized"] is False
    assert any(
        row["outcome_status"] == "INSUFFICIENT_DATA"
        and row["outcome_reason_codes"] == ["reference_price_unavailable"]
        for row in terminal.json()["decision_outcomes"]
    )

    performance = client.get(f"{base}/performance")
    assert performance.status_code == 200
    assert performance.json()["strategy"]["total_return"] is None
    assert "experiment_equity_curve_unavailable_n3_4" in performance.json()["strategy"]["reason_codes"]
    assert performance.json()["benchmark"]["portfolio_excess_return"] is None
    assert "experiment_and_benchmark_equity_curves_unavailable_n3_5" in performance.json()["benchmark"]["reason_codes"]

    breakdown = client.get(f"{base}/breakdown")
    assert breakdown.status_code == 200
    assert breakdown.json()["action_breakdown"][0]["action"] == "BUY"
    assert breakdown.json()["regime_breakdown"][0]["market_regime"] == "range"
    assert any(
        row["disposition"] == "EXECUTED" and row["resolved_count"] == 1
        for row in breakdown.json()["execution_attribution"]
    )
    assert breakdown.json()["benchmark_horizon_breakdown"][0]["resolved_count"] == 1
    assert client.get("/v1/lab/calibration").status_code == 404
