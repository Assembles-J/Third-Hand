from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import sqlite3
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.application_services.evaluation import StrategyEvaluationService
from app.domain.evaluation import (
    ActionOutcomeClass,
    DecisionOutcome,
    EvaluationPolicy,
    ExecutionDisposition,
    ExecutionOutcome,
    OutcomeStatus,
    SampleQualityPolicy,
    SampleQualityState,
    TradeEpisodeOutcome,
)
from app.domain.experiment import ExperimentUniverseSnapshot
from app.infrastructure.database.evaluation_outcome_repository import EvaluationOutcomeRepository
from app.infrastructure.database.strategy_evaluation_repository import StrategyEvaluationRepository

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
    captured_at=datetime(2026, 1, 5, 9, 0, tzinfo=TZ),
    members=({"symbol": "600519", "market": "CN"},),
)


def _experiment():
    return SimpleNamespace(
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        outcome_policy_version="1.0.0",
        evaluation_policy_version="test-eval-v1",
        sample_quality_policy_version="test-sample-v1",
        universe_policy_version=UNIVERSE.universe_policy_version,
        universe_snapshot_id=UNIVERSE.universe_snapshot_id,
        universe_snapshot_hash=UNIVERSE.snapshot_hash,
        universe_snapshot=UNIVERSE,
    )


def _evaluation_policy():
    return EvaluationPolicy(
        policy_id="test-eval",
        version="test-eval-v1",
        decision_count_rule="unique_decision_with_any_resolved_horizon_v1",
        action_breakdown_rule="action_and_horizon_resolved_rows_v1",
        regime_breakdown_rule="regime_and_horizon_resolved_rows_v1",
        episode_metric_rule="closed_episode_net_return_and_realized_pnl_v1",
        portfolio_return_rule="require_experiment_equity_curve_no_episode_compound_proxy_v1",
        nonresolved_ratio_rule="terminal_decision_outcome_rows_v1",
    )


def _sample_policy():
    return SampleQualityPolicy(
        policy_id="test-sample",
        version="test-sample-v1",
        low_min_resolved_decisions=1,
        low_min_distinct_symbols=1,
        usable_min_resolved_decisions=2,
        usable_min_completed_episodes=2,
        usable_min_distinct_symbols=1,
        usable_max_nonresolved_ratio=Decimal("0.5"),
        strong_min_resolved_decisions=4,
        strong_min_completed_episodes=4,
        strong_min_distinct_symbols=2,
        strong_max_nonresolved_ratio=Decimal("0.1"),
    )


def _decision(decision_id, *, action, horizon, forward, outcome_class, regime="range"):
    decision_time = datetime(2026, 1, 5, 10, 0, tzinfo=TZ)
    observation_end = datetime(2026, 1, 20, 15, 0, tzinfo=TZ)
    return DecisionOutcome(
        outcome_id=f"{decision_id}:h{horizon}",
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        decision_id=decision_id,
        symbol="600519",
        market="CN",
        action=action,
        decision_time=decision_time,
        reference_price=Decimal("100"),
        horizon_sessions=horizon,
        observation_end=observation_end,
        outcome_status=OutcomeStatus.RESOLVED,
        forward_return=Decimal(forward),
        mfe=Decimal("0.10"),
        mae=Decimal("-0.04"),
        market_regime=regime,
        action_outcome_class=ActionOutcomeClass(outcome_class),
        outcome_policy_version="1.0.0",
        source_lineage_hash=f"hash-{decision_id}-{horizon}",
        resolved_at=datetime(2026, 1, 20, 16, 0, tzinfo=TZ),
    )


def _episode(episode_id, *, net_return, pnl, closed_day):
    return TradeEpisodeOutcome(
        episode_outcome_id=episode_id,
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        position_episode_id=episode_id,
        symbol="600519",
        outcome_status=OutcomeStatus.RESOLVED,
        opened_at=datetime(2026, 1, 5, 10, 0, tzinfo=TZ),
        closed_at=datetime(2026, 1, closed_day, 14, 0, tzinfo=TZ),
        holding_sessions=5,
        gross_return=Decimal(net_return) + Decimal("0.002"),
        net_return=Decimal(net_return),
        realized_pnl=Decimal(pnl),
        fees=Decimal("2"),
        slippage=Decimal("0"),
        mfe=Decimal("0.12"),
        mae=Decimal("-0.05"),
        episode_max_drawdown=Decimal("-0.06"),
        entry_decision_ids=(f"{episode_id}-buy",),
        position_decision_ids=(f"{episode_id}-exit",),
        fill_ids=(f"{episode_id}-b", f"{episode_id}-s"),
        outcome_policy_version="1.0.0",
        source_lineage_hash=f"hash-{episode_id}",
        resolved_at=datetime(2026, 1, closed_day, 16, 0, tzinfo=TZ),
    )


def test_strategy_evaluation_aggregates_terminal_outcomes_without_fake_portfolio_return(tmp_path):
    store = SQLiteStore(tmp_path / "evaluation.db")
    outcomes = EvaluationOutcomeRepository(store)
    evaluations = StrategyEvaluationRepository(store)

    outcomes.save_decision(_decision("d1", action="BUY", horizon=3, forward="0.10", outcome_class="FAVORABLE"))
    outcomes.save_decision(_decision("d1", action="BUY", horizon=5, forward="0.05", outcome_class="FAVORABLE"))
    outcomes.save_decision(_decision("d2", action="WAIT", horizon=3, forward="-0.02", outcome_class="FAVORABLE"))
    outcomes.save_execution(ExecutionOutcome(
        execution_outcome_id="d1:execution",
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        decision_id="d1",
        requested_action="BUY",
        outcome_status=OutcomeStatus.RESOLVED,
        execution_disposition=ExecutionDisposition.EXECUTED,
        requested_quantity=Decimal("100"),
        max_executable_quantity=Decimal("100"),
        executed_quantity=Decimal("100"),
        fill_ids=("fill-1",),
        resolved_at=datetime(2026, 1, 5, 10, 1, tzinfo=TZ),
        source_lineage_hash="execution-1",
    ))
    outcomes.save_execution(ExecutionOutcome(
        execution_outcome_id="d2:execution",
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        decision_id="d2",
        requested_action="WAIT",
        outcome_status=OutcomeStatus.RESOLVED,
        execution_disposition=ExecutionDisposition.NOT_APPLICABLE,
        resolved_at=datetime(2026, 1, 5, 10, 1, tzinfo=TZ),
        source_lineage_hash="execution-2",
    ))
    outcomes.save_episode(_episode("ep1", net_return="0.10", pnl="100", closed_day=10))
    outcomes.save_episode(_episode("ep2", net_return="-0.05", pnl="-40", closed_day=20))

    service = StrategyEvaluationService(
        outcomes,
        evaluation_repository=evaluations,
        evaluation_policy=_evaluation_policy(),
        sample_quality_policy=_sample_policy(),
    )
    result = service.evaluate(
        _experiment(),
        computed_at=datetime(2026, 2, 1, 12, 0, tzinfo=TZ),
    )

    assert result.universe_snapshot_id == UNIVERSE.universe_snapshot_id
    assert result.universe_snapshot_hash == UNIVERSE.snapshot_hash
    assert result.resolved_decision_count == 2
    assert result.decision_outcome_row_count == 3
    assert result.completed_trade_count == 2
    assert result.sample_quality == SampleQualityState.USABLE
    assert result.win_rate == Decimal("0.5")
    assert result.average_win == Decimal("0.10")
    assert result.average_loss == Decimal("-0.05")
    assert result.payoff_ratio == Decimal("2")
    assert result.expectancy == Decimal("0.025")
    assert result.profit_factor == Decimal("2.5")
    assert result.max_consecutive_losses == 1
    assert result.total_fees == Decimal("4")
    assert result.total_return is None
    assert result.max_drawdown is None
    assert result.portfolio_metric_reason_codes == (
        "experiment_equity_curve_unavailable_n3_4",
    )
    assert {(item.action, item.horizon_sessions) for item in result.action_breakdown} == {
        ("BUY", 3),
        ("BUY", 5),
        ("WAIT", 3),
    }
    assert [item.horizon_sessions for item in result.horizon_breakdown] == [3, 5]
    assert evaluations.get(result.evaluation_id).contract_hash == result.contract_hash


def test_evaluation_source_hash_is_order_independent_and_snapshot_ids_are_immutable(tmp_path):
    first_store = SQLiteStore(tmp_path / "a.db")
    second_store = SQLiteStore(tmp_path / "b.db")
    first = EvaluationOutcomeRepository(first_store)
    second = EvaluationOutcomeRepository(second_store)
    rows = [
        _decision("d1", action="BUY", horizon=3, forward="0.04", outcome_class="FAVORABLE"),
        _decision("d2", action="WAIT", horizon=3, forward="-0.03", outcome_class="FAVORABLE"),
    ]
    for item in rows:
        first.save_decision(item)
    for item in reversed(rows):
        second.save_decision(item)

    service_a = StrategyEvaluationService(
        first,
        evaluation_policy=_evaluation_policy(),
        sample_quality_policy=_sample_policy(),
    )
    service_b = StrategyEvaluationService(
        second,
        evaluation_policy=_evaluation_policy(),
        sample_quality_policy=_sample_policy(),
    )
    at = datetime(2026, 2, 1, 12, 0, tzinfo=TZ)
    a = service_a.evaluate(_experiment(), computed_at=at)
    b = service_b.evaluate(_experiment(), computed_at=at)
    assert a.source_hash == b.source_hash
    assert a.evaluation_id == b.evaluation_id

    later = service_a.evaluate(
        _experiment(),
        computed_at=datetime(2026, 2, 2, 12, 0, tzinfo=TZ),
    )
    assert later.source_hash == a.source_hash
    assert later.evaluation_id != a.evaluation_id


def test_sample_quality_policy_is_versioned_sufficiency_not_performance_rating():
    policy = _sample_policy()
    assert policy.classify(
        resolved_decisions=1,
        completed_episodes=0,
        distinct_symbols=1,
        nonresolved_ratio=Decimal("0.9"),
    ) == SampleQualityState.LOW
    assert policy.classify(
        resolved_decisions=2,
        completed_episodes=2,
        distinct_symbols=1,
        nonresolved_ratio=Decimal("0.5"),
    ) == SampleQualityState.USABLE
    with pytest.raises(ValueError, match="strong decision threshold"):
        SampleQualityPolicy(
            policy_id="bad",
            version="1",
            low_min_resolved_decisions=10,
            low_min_distinct_symbols=1,
            usable_min_resolved_decisions=20,
            usable_min_completed_episodes=5,
            usable_min_distinct_symbols=2,
            usable_max_nonresolved_ratio=Decimal("0.2"),
            strong_min_resolved_decisions=19,
            strong_min_completed_episodes=10,
            strong_min_distinct_symbols=3,
            strong_max_nonresolved_ratio=Decimal("0.1"),
        )

def test_strategy_evaluation_rejects_outcome_outside_frozen_universe(tmp_path):
    store = SQLiteStore(tmp_path / "outside.db")
    outcomes = EvaluationOutcomeRepository(store)
    outside = _decision("outside", action="BUY", horizon=3, forward="0.04", outcome_class="FAVORABLE").model_copy(update={"symbol": "000001"})
    outcomes.save_decision(outside)
    service = StrategyEvaluationService(
        outcomes,
        evaluation_policy=_evaluation_policy(),
        sample_quality_policy=_sample_policy(),
    )
    with pytest.raises(ValueError, match="outside frozen experiment universe"):
        service.evaluate(_experiment(), computed_at=datetime(2026, 2, 1, 12, 0, tzinfo=TZ))

