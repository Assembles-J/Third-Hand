from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import sqlite3
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.application_services.evaluation import BenchmarkEvaluationService
from app.domain.evaluation import (
    ActionOutcomeClass,
    BenchmarkConstituentSource,
    BenchmarkPolicy,
    BenchmarkType,
    DecisionOutcome,
    OutcomeStatus,
)
from app.domain.experiment import ExperimentUniverseSnapshot
from app.infrastructure.database.benchmark_evaluation_repository import BenchmarkEvaluationRepository
from app.infrastructure.database.evaluation_outcome_repository import EvaluationOutcomeRepository

TZ = ZoneInfo("Asia/Shanghai")


class SQLiteStore:
    def __init__(self, path):
        self.path = path

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


UNIVERSE = ExperimentUniverseSnapshot(
    universe_snapshot_id="formal-swing-v1-forward:1.0.0:universe",
    experiment_id="formal-swing-v1-forward",
    experiment_version="1.0.0",
    universe_policy_version="explicit-forward-universe-v1",
    captured_at=datetime(2026, 1, 2, 16, 0, tzinfo=TZ),
    members=(
        {"symbol": "600519", "market": "CN"},
        {"symbol": "000001", "market": "CN"},
        {"symbol": "01810", "market": "HK"},
    ),
)


def _experiment(*, benchmark_policy_version="benchmark-equal-v1"):
    return SimpleNamespace(
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        benchmark_policy_version=benchmark_policy_version,
        universe_policy_version=UNIVERSE.universe_policy_version,
        universe_snapshot_id=UNIVERSE.universe_snapshot_id,
        universe_snapshot_hash=UNIVERSE.snapshot_hash,
        universe_snapshot=UNIVERSE,
    )


def _decision(
    outcome_id="d1:h3",
    *,
    decision_id="d1",
    symbol="600519",
    market="CN",
    forward="0.10",
    horizon=3,
    decision_time=None,
    observation_end=None,
):
    decision_time = decision_time or datetime(2026, 1, 5, 10, 0, tzinfo=TZ)
    observation_end = observation_end or datetime(2026, 1, 8, 15, 0, tzinfo=TZ)
    return DecisionOutcome(
        outcome_id=outcome_id,
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        decision_id=decision_id,
        symbol=symbol,
        market=market,
        action="BUY",
        decision_time=decision_time,
        reference_price=Decimal("100"),
        horizon_sessions=horizon,
        observation_end=observation_end,
        outcome_status=OutcomeStatus.RESOLVED,
        forward_return=Decimal(forward),
        mfe=Decimal("0.12"),
        mae=Decimal("-0.03"),
        action_outcome_class=ActionOutcomeClass.FAVORABLE,
        outcome_policy_version="1.0.0",
        source_lineage_hash="a" * 64,
        resolved_at=observation_end,
    )


class FakeSource:
    def __init__(self):
        self.rows: dict[str, list[dict[str, object]]] = {}

    def daily_bars_between(self, symbol, start_date, end_date):
        return tuple(
            row
            for row in self.rows.get(symbol, ())
            if start_date <= row["trading_date"] <= end_date
        )


def bar(day, close, *, adjustment="qfq"):
    return {
        "trading_date": day,
        "open": str(close),
        "close": str(close),
        "high": str(close),
        "low": str(close),
        "adjustment": adjustment,
        "source": "local-test",
        "updated_at": f"{day}T16:00:00+08:00",
    }


class FakeCalendar:
    def latest_completed_session_date(self, market, moment):
        if moment.date().isoformat() == "2026-01-05" and moment.hour < 15:
            return "2026-01-02"
        return moment.date().isoformat()


def _equal_policy():
    return BenchmarkPolicy(
        benchmark_policy_id="swing-v1-equal-weight",
        version="benchmark-equal-v1",
        benchmark_type=BenchmarkType.EQUAL_WEIGHT_ELIGIBLE_UNIVERSE,
        constituent_source=BenchmarkConstituentSource.EXPERIMENT_UNIVERSE,
    )


def test_equal_weight_benchmark_uses_frozen_same_market_members_and_no_portfolio_proxy(tmp_path):
    store = SQLiteStore(tmp_path / "benchmark.db")
    outcomes = EvaluationOutcomeRepository(store)
    benchmark_repo = BenchmarkEvaluationRepository(store)
    outcomes.save_decision(_decision())

    source = FakeSource()
    source.rows = {
        "600519": [bar("2026-01-02", 100), bar("2026-01-08", 110)],
        "000001": [bar("2026-01-02", 20), bar("2026-01-08", 21)],
        # HK member is intentionally ignored for a CN decision benchmark.
        "01810": [bar("2026-01-02", 30), bar("2026-01-08", 60)],
    }
    service = BenchmarkEvaluationService(
        outcomes,
        source,
        benchmark_repository=benchmark_repo,
        trading_calendar=FakeCalendar(),
    )
    result = service.evaluate(
        _experiment(),
        _equal_policy(),
        computed_at=datetime(2026, 1, 9, 12, 0, tzinfo=TZ),
    )

    assert result.resolved_observation_count == 1
    assert result.nonresolved_observation_count == 0
    assert result.mean_strategy_forward_return == Decimal("0.10")
    assert result.mean_benchmark_forward_return == Decimal("0.075")
    assert result.mean_excess_forward_return == Decimal("0.025")
    assert result.portfolio_benchmark_return is None
    assert result.portfolio_excess_return is None
    assert result.portfolio_metric_reason_codes == (
        "experiment_and_benchmark_equity_curves_unavailable_n3_5",
    )

    observation = benchmark_repo.list_observations(
        "formal-swing-v1-forward",
        "1.0.0",
        "benchmark-equal-v1",
    )[0]
    assert observation.reference_session == "2026-01-02"
    assert observation.end_session == "2026-01-08"
    assert observation.constituent_count == 2
    assert observation.universe_snapshot_hash == UNIVERSE.snapshot_hash
    assert benchmark_repo.get_evaluation(result.benchmark_evaluation_id) == result


def test_equal_weight_benchmark_fails_closed_when_one_frozen_constituent_is_missing(tmp_path):
    store = SQLiteStore(tmp_path / "missing.db")
    outcomes = EvaluationOutcomeRepository(store)
    outcomes.save_decision(_decision())
    source = FakeSource()
    source.rows = {
        "600519": [bar("2026-01-02", 100), bar("2026-01-08", 110)],
        "000001": [bar("2026-01-02", 20)],
    }
    result = BenchmarkEvaluationService(
        outcomes,
        source,
        trading_calendar=FakeCalendar(),
    ).evaluate(
        _experiment(),
        _equal_policy(),
        computed_at=datetime(2026, 1, 9, 12, 0, tzinfo=TZ),
    )
    assert result.resolved_observation_count == 0
    assert result.nonresolved_observation_count == 1
    assert result.mean_benchmark_forward_return is None
    assert result.horizon_breakdown[0].nonresolved_count == 1


def test_explicit_market_benchmark_rejects_cross_market_decision_instead_of_reusing_cn_index(tmp_path):
    store = SQLiteStore(tmp_path / "market.db")
    outcomes = EvaluationOutcomeRepository(store)
    outcomes.save_decision(
        _decision(
            outcome_id="hk:h3",
            decision_id="hk",
            symbol="01810",
            market="HK",
            forward="0.08",
        )
    )
    policy = BenchmarkPolicy(
        benchmark_policy_id="cn-index",
        version="benchmark-cn-v1",
        benchmark_type=BenchmarkType.MARKET_INDEX,
        constituent_source=BenchmarkConstituentSource.EXPLICIT_SYMBOL,
        benchmark_market="CN",
        benchmark_symbol="000300",
    )
    result = BenchmarkEvaluationService(
        outcomes,
        FakeSource(),
        trading_calendar=FakeCalendar(),
    ).evaluate(
        _experiment(benchmark_policy_version="benchmark-cn-v1"),
        policy,
        computed_at=datetime(2026, 1, 9, 12, 0, tzinfo=TZ),
    )
    assert result.resolved_observation_count == 0
    assert result.nonresolved_observation_count == 1


def test_explicit_symbol_and_neutral_benchmarks_are_versioned_and_point_in_time_safe(tmp_path):
    store = SQLiteStore(tmp_path / "explicit.db")
    outcomes = EvaluationOutcomeRepository(store)
    outcomes.save_decision(_decision())
    source = FakeSource()
    source.rows["000300"] = [bar("2026-01-02", 4000), bar("2026-01-08", 4080)]

    index_policy = BenchmarkPolicy(
        benchmark_policy_id="csi300-explicit",
        version="benchmark-index-v1",
        benchmark_type=BenchmarkType.MARKET_INDEX,
        constituent_source=BenchmarkConstituentSource.EXPLICIT_SYMBOL,
        benchmark_market="CN",
        benchmark_symbol="000300",
    )
    result = BenchmarkEvaluationService(
        outcomes,
        source,
        trading_calendar=FakeCalendar(),
    ).evaluate(
        _experiment(benchmark_policy_version="benchmark-index-v1"),
        index_policy,
        computed_at=datetime(2026, 1, 9, 12, 0, tzinfo=TZ),
    )
    assert result.mean_benchmark_forward_return == Decimal("0.02")
    assert result.mean_excess_forward_return == Decimal("0.08")

    neutral = BenchmarkPolicy(
        benchmark_policy_id="zero-diagnostic",
        version="benchmark-neutral-v1",
        benchmark_type=BenchmarkType.NEUTRAL_DIAGNOSTIC,
        constituent_source=BenchmarkConstituentSource.NONE,
    )
    neutral_result = BenchmarkEvaluationService(
        outcomes,
        source,
        trading_calendar=FakeCalendar(),
    ).evaluate(
        _experiment(benchmark_policy_version="benchmark-neutral-v1"),
        neutral,
        computed_at=datetime(2026, 1, 9, 12, 0, tzinfo=TZ),
    )
    assert neutral_result.mean_benchmark_forward_return == Decimal("0")
    assert neutral_result.mean_excess_forward_return == Decimal("0.10")


def test_formal_reference_policy_is_explicitly_deferred_to_evaluation_compare(tmp_path):
    store = SQLiteStore(tmp_path / "formal.db")
    outcomes = EvaluationOutcomeRepository(store)
    outcomes.save_decision(_decision())
    policy = BenchmarkPolicy(
        benchmark_policy_id="formal-reference",
        version="benchmark-formal-v1",
        benchmark_type=BenchmarkType.FORMAL_SWING_V1,
        constituent_source=BenchmarkConstituentSource.REFERENCE_EXPERIMENT,
        reference_experiment_id="formal-baseline",
        reference_experiment_version="1.0.0",
    )
    result = BenchmarkEvaluationService(
        outcomes,
        FakeSource(),
        trading_calendar=FakeCalendar(),
    ).evaluate(
        _experiment(benchmark_policy_version="benchmark-formal-v1"),
        policy,
        computed_at=datetime(2026, 1, 9, 12, 0, tzinfo=TZ),
    )
    assert result.resolved_observation_count == 0
    assert result.nonresolved_observation_count == 1


def test_policy_rejects_implicit_or_mismatched_constituent_contracts():
    with pytest.raises(ValueError, match="benchmark_market"):
        BenchmarkPolicy(
            benchmark_policy_id="bad-index",
            version="v1",
            benchmark_type=BenchmarkType.MARKET_INDEX,
            constituent_source=BenchmarkConstituentSource.EXPLICIT_SYMBOL,
            benchmark_symbol="000300",
        )
    with pytest.raises(ValueError, match="EXPERIMENT_UNIVERSE"):
        BenchmarkPolicy(
            benchmark_policy_id="bad-equal",
            version="v1",
            benchmark_type=BenchmarkType.EQUAL_WEIGHT_ELIGIBLE_UNIVERSE,
            constituent_source=BenchmarkConstituentSource.EXPLICIT_SYMBOL,
        )
