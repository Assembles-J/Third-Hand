from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.evaluation import (
    ActionOutcomeClass,
    ActionOutcomeDimension,
    DecisionOutcome,
    ExecutionDisposition,
    ExecutionOutcome,
    OutcomePolicy,
    OutcomeStatus,
    TargetStopRule,
    TradeEpisodeOutcome,
    swing_v1_action_outcome_policy,
    swing_v1_outcome_policy,
)


T0 = datetime(2026, 8, 20, 3, 0, tzinfo=timezone.utc)
T10 = T0 + timedelta(days=14)


def _decision(**overrides):
    payload = {
        "outcome_id": "outcome-1",
        "experiment_id": "formal-swing-v1-forward",
        "experiment_version": "1.0.0",
        "decision_id": "decision-1",
        "symbol": "600519",
        "market": "CN_A",
        "action": "BUY",
        "decision_time": T0,
        "reference_price": Decimal("100.00"),
        "horizon_sessions": 10,
        "observation_end": T10,
        "outcome_status": OutcomeStatus.PENDING,
        "outcome_policy_version": "1.0.0",
    }
    payload.update(overrides)
    return DecisionOutcome(**payload)


def test_swing_v1_policy_is_explicit_for_every_formal_action():
    action_policy = swing_v1_action_outcome_policy()
    outcome_policy = swing_v1_outcome_policy()

    assert tuple(rule.action for rule in action_policy.rules) == (
        "BUY", "WAIT", "HOLD", "ADD", "REDUCE", "EXIT", "BLOCKED"
    )
    assert ActionOutcomeDimension.ENTRY_QUALITY in action_policy.rule_for("BUY").dimensions
    assert ActionOutcomeDimension.MISSED_OPPORTUNITY in action_policy.rule_for("WAIT").dimensions
    assert ActionOutcomeDimension.EXIT_QUALITY in action_policy.rule_for("EXIT").dimensions
    assert ActionOutcomeDimension.GATE_CORRECTNESS in action_policy.rule_for("BLOCKED").dimensions
    assert outcome_policy.decision_horizons == (3, 5, 10, 20)
    assert outcome_policy.target_stop_rules == ()
    assert action_policy.contract_hash == swing_v1_action_outcome_policy().contract_hash


def test_target_stop_rules_are_versioned_and_must_use_declared_horizons():
    with pytest.raises(ValidationError):
        OutcomePolicy(
            policy_id="outcome-test",
            version="1.0.0",
            decision_horizons=(3, 5, 10, 20),
            action_outcome_policy_id="action-outcome-test",
            action_outcome_policy_version="1.0.0",
            target_stop_rules=(
                TargetStopRule(
                    action="BUY",
                    horizon_sessions=30,
                    target_return=Decimal("0.06"),
                    stop_return=Decimal("-0.03"),
                ),
            ),
            benchmark_alignment_rule="same_window",
            trading_calendar_rule="market_calendar",
            missing_data_rule="exclude",
            suspended_symbol_rule="explicit",
            corporate_action_adjustment_rule="point_in_time",
        )


def test_pending_decision_outcome_cannot_be_scored_early():
    pending = _decision()
    assert pending.outcome_status == OutcomeStatus.PENDING

    with pytest.raises(ValidationError):
        _decision(forward_return=Decimal("0.04"))

    with pytest.raises(ValidationError):
        _decision(resolved_at=T10, source_lineage_hash="future-data")


def test_resolved_decision_requires_complete_metrics_and_terminal_lineage():
    resolved = _decision(
        outcome_status=OutcomeStatus.RESOLVED,
        forward_return=Decimal("0.052"),
        mfe=Decimal("0.081"),
        mae=Decimal("-0.017"),
        action_outcome_class=ActionOutcomeClass.FAVORABLE,
        source_lineage_hash="market-window-hash",
        resolved_at=T10 + timedelta(minutes=1),
    )

    assert resolved.forward_return == Decimal("0.052")
    assert resolved.contract_hash == DecisionOutcome(**resolved.model_dump()).contract_hash

    with pytest.raises(ValidationError):
        _decision(
            outcome_status=OutcomeStatus.RESOLVED,
            forward_return=Decimal("0.052"),
            mfe=Decimal("0.081"),
            source_lineage_hash="market-window-hash",
            resolved_at=T10 + timedelta(minutes=1),
        )


def test_invalid_or_insufficient_decisions_are_terminal_but_not_scoreable():
    insufficient = _decision(
        outcome_status=OutcomeStatus.INSUFFICIENT_DATA,
        outcome_reason_codes=("market_history_gap",),
        source_lineage_hash="gap-lineage",
        resolved_at=T10 + timedelta(minutes=1),
    )
    assert insufficient.forward_return is None

    with pytest.raises(ValidationError):
        _decision(
            outcome_status=OutcomeStatus.INVALID,
            outcome_reason_codes=("lookahead_detected",),
            source_lineage_hash="invalid-lineage",
            resolved_at=T10 + timedelta(minutes=1),
            forward_return=Decimal("0.10"),
        )


def test_execution_outcome_separates_non_execution_from_blocks_and_deferrals():
    wait = ExecutionOutcome(
        execution_outcome_id="exec-wait",
        experiment_id="exp",
        experiment_version="1.0.0",
        decision_id="d-wait",
        requested_action="WAIT",
        outcome_status=OutcomeStatus.RESOLVED,
        execution_disposition=ExecutionDisposition.NOT_APPLICABLE,
        resolved_at=T0,
        source_lineage_hash="decision-lineage",
    )
    assert wait.execution_disposition == ExecutionDisposition.NOT_APPLICABLE

    deferred = ExecutionOutcome(
        execution_outcome_id="exec-exit",
        experiment_id="exp",
        experiment_version="1.0.0",
        decision_id="d-exit",
        requested_action="EXIT",
        outcome_status=OutcomeStatus.RESOLVED,
        execution_disposition=ExecutionDisposition.DEFERRED,
        requested_quantity=Decimal("100"),
        max_executable_quantity=Decimal("0"),
        executed_quantity=Decimal("0"),
        execution_reason_codes=("LOT_LOCKED_T1",),
        deferral_id="deferral-1",
        resolved_at=T0,
        source_lineage_hash="execution-lineage",
    )
    assert deferred.executed_quantity == 0

    with pytest.raises(ValidationError):
        ExecutionOutcome(
            execution_outcome_id="bad-wait",
            experiment_id="exp",
            experiment_version="1.0.0",
            decision_id="d-wait",
            requested_action="WAIT",
            outcome_status=OutcomeStatus.RESOLVED,
            execution_disposition=ExecutionDisposition.EXECUTED,
            executed_quantity=Decimal("100"),
            fill_ids=("fill-1",),
            resolved_at=T0,
            source_lineage_hash="bad",
        )


def test_trade_episode_does_not_score_open_or_incomplete_episodes():
    pending = TradeEpisodeOutcome(
        episode_outcome_id="episode-outcome-1",
        experiment_id="exp",
        experiment_version="1.0.0",
        position_episode_id="episode-1",
        symbol="600519",
        outcome_status=OutcomeStatus.PENDING,
        opened_at=T0,
        entry_decision_ids=("decision-buy",),
        fill_ids=("fill-buy",),
        outcome_policy_version="1.0.0",
    )
    assert pending.net_return is None

    resolved = TradeEpisodeOutcome(
        episode_outcome_id="episode-outcome-2",
        experiment_id="exp",
        experiment_version="1.0.0",
        position_episode_id="episode-2",
        symbol="600519",
        outcome_status=OutcomeStatus.RESOLVED,
        opened_at=T0,
        closed_at=T10,
        holding_sessions=10,
        gross_return=Decimal("0.08"),
        net_return=Decimal("0.074"),
        realized_pnl=Decimal("740.00"),
        fees=Decimal("20.00"),
        slippage=Decimal("40.00"),
        mfe=Decimal("0.11"),
        mae=Decimal("-0.02"),
        episode_max_drawdown=Decimal("-0.025"),
        entry_decision_ids=("decision-buy",),
        position_decision_ids=("decision-hold", "decision-exit"),
        fill_ids=("fill-buy", "fill-exit"),
        outcome_policy_version="1.0.0",
        source_lineage_hash="episode-lineage",
        resolved_at=T10 + timedelta(minutes=1),
    )
    assert resolved.net_return == Decimal("0.074")

    with pytest.raises(ValidationError):
        TradeEpisodeOutcome(
            episode_outcome_id="episode-bad",
            experiment_id="exp",
            experiment_version="1.0.0",
            position_episode_id="episode-bad",
            symbol="600519",
            outcome_status=OutcomeStatus.PENDING,
            opened_at=T0,
            closed_at=T10,
            net_return=Decimal("0.05"),
            outcome_policy_version="1.0.0",
        )
