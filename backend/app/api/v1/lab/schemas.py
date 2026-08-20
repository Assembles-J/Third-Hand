"""Stable read-only DTOs for the N3 Lab API.

These models are intentionally presentation contracts. They expose immutable
Evaluation facts without granting any Formal Decision, Risk, sizing, execution,
or provider-refresh authority.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LabDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LabExperimentItem(LabDto):
    experiment_id: str
    experiment_version: str
    experiment_type: str
    status: str
    strategy_id: str
    strategy_version: str
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
    universe_snapshot_id: str
    universe_snapshot_hash: str
    universe_policy_version: str
    outcome_policy_version: str
    benchmark_policy_version: str
    sample_quality_policy_version: str
    evaluation_policy_version: str


class LabExperimentListResponse(LabDto):
    items: tuple[LabExperimentItem, ...]
    count: int = Field(ge=0)


class LabUniverseMember(LabDto):
    market: str
    symbol: str


class LabExperimentDetailResponse(LabDto):
    experiment: LabExperimentItem
    selection_mode: Literal["explicit_version", "latest_version"]
    universe_member_count: int = Field(ge=0)
    universe_members: tuple[LabUniverseMember, ...]
    definition_hash: str


class LabOutcomeCounts(LabDto):
    decision_terminal_count: int = Field(ge=0)
    decision_resolved_count: int = Field(ge=0)
    decision_insufficient_count: int = Field(ge=0)
    decision_invalid_count: int = Field(ge=0)
    execution_terminal_count: int = Field(ge=0)
    execution_resolved_count: int = Field(ge=0)
    execution_insufficient_count: int = Field(ge=0)
    execution_invalid_count: int = Field(ge=0)
    episode_terminal_count: int = Field(ge=0)
    episode_resolved_count: int = Field(ge=0)
    episode_insufficient_count: int = Field(ge=0)
    episode_invalid_count: int = Field(ge=0)
    pending_decision_count: int | None = None
    pending_count_reason: str | None = None


class LabStrategySummary(LabDto):
    available: bool
    evaluation_id: str | None = None
    computed_at: datetime | None = None
    sample_quality: str | None = None
    resolved_decision_count: int | None = None
    completed_trade_count: int | None = None
    distinct_symbol_count: int | None = None
    reason_codes: tuple[str, ...] = ()


class LabBenchmarkSummary(LabDto):
    available: bool
    benchmark_evaluation_id: str | None = None
    benchmark_policy_id: str | None = None
    benchmark_policy_version: str | None = None
    benchmark_type: str | None = None
    computed_at: datetime | None = None
    resolved_observation_count: int | None = None
    nonresolved_observation_count: int | None = None
    reason_codes: tuple[str, ...] = ()


class LabSummaryResponse(LabDto):
    experiment: LabExperimentItem
    outcome_counts: LabOutcomeCounts
    strategy: LabStrategySummary
    benchmark: LabBenchmarkSummary


class LabDecisionOutcomeItem(LabDto):
    outcome_id: str
    decision_id: str
    symbol: str
    market: str
    action: str
    horizon_sessions: int
    outcome_status: str
    decision_time: datetime
    observation_end: datetime
    forward_return: Decimal | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None
    market_regime: str | None = None
    action_outcome_class: str | None = None
    outcome_reason_codes: tuple[str, ...] = ()
    resolved_at: datetime | None = None


class LabExecutionOutcomeItem(LabDto):
    execution_outcome_id: str
    decision_id: str
    requested_action: str
    outcome_status: str
    execution_disposition: str
    requested_quantity: Decimal | None = None
    max_executable_quantity: Decimal | None = None
    executed_quantity: Decimal | None = None
    deferral_id: str | None = None
    fill_count: int = Field(ge=0)
    execution_reason_codes: tuple[str, ...] = ()
    resolved_at: datetime | None = None


class LabTradeEpisodeOutcomeItem(LabDto):
    episode_outcome_id: str
    position_episode_id: str
    symbol: str
    outcome_status: str
    opened_at: datetime
    closed_at: datetime | None = None
    holding_sessions: int | None = None
    net_return: Decimal | None = None
    realized_pnl: Decimal | None = None
    fees: Decimal | None = None
    slippage: Decimal | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None
    episode_max_drawdown: Decimal | None = None
    outcome_reason_codes: tuple[str, ...] = ()
    resolved_at: datetime | None = None


class LabOutcomesResponse(LabDto):
    experiment_id: str
    experiment_version: str
    terminal_only: bool = True
    pending_materialized: bool = False
    pending_reason: str = "pending_outcomes_are_derived_not_materialized_n3_6"
    decision_outcomes: tuple[LabDecisionOutcomeItem, ...]
    execution_outcomes: tuple[LabExecutionOutcomeItem, ...]
    trade_episode_outcomes: tuple[LabTradeEpisodeOutcomeItem, ...]


class LabStrategyPerformance(LabDto):
    available: bool
    evaluation_id: str | None = None
    computed_at: datetime | None = None
    sample_quality: str | None = None
    resolved_decision_count: int | None = None
    completed_trade_count: int | None = None
    distinct_symbol_count: int | None = None
    total_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    turnover: Decimal | None = None
    win_rate: Decimal | None = None
    average_win: Decimal | None = None
    average_loss: Decimal | None = None
    payoff_ratio: Decimal | None = None
    expectancy: Decimal | None = None
    profit_factor: Decimal | None = None
    max_consecutive_losses: int | None = None
    average_holding_sessions: Decimal | None = None
    total_fees: Decimal | None = None
    total_slippage: Decimal | None = None
    average_episode_net_return: Decimal | None = None
    worst_episode_drawdown: Decimal | None = None
    reason_codes: tuple[str, ...] = ()


class LabBenchmarkPerformance(LabDto):
    available: bool
    benchmark_evaluation_id: str | None = None
    benchmark_policy_id: str | None = None
    benchmark_policy_version: str | None = None
    benchmark_type: str | None = None
    computed_at: datetime | None = None
    resolved_observation_count: int | None = None
    nonresolved_observation_count: int | None = None
    mean_strategy_forward_return: Decimal | None = None
    mean_benchmark_forward_return: Decimal | None = None
    mean_excess_forward_return: Decimal | None = None
    portfolio_benchmark_return: Decimal | None = None
    portfolio_excess_return: Decimal | None = None
    reason_codes: tuple[str, ...] = ()


class LabPerformanceResponse(LabDto):
    experiment: LabExperimentItem
    strategy: LabStrategyPerformance
    benchmark: LabBenchmarkPerformance


class LabDecisionBreakdownItem(LabDto):
    action: str | None = None
    market_regime: str | None = None
    horizon_sessions: int
    sample_count: int = Field(ge=0)
    favorable_count: int = Field(ge=0)
    unfavorable_count: int = Field(ge=0)
    mixed_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    mean_forward_return: Decimal | None = None
    mean_mfe: Decimal | None = None
    mean_mae: Decimal | None = None


class LabExecutionBreakdownItem(LabDto):
    disposition: str
    count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    nonresolved_count: int = Field(ge=0)


class LabBenchmarkHorizonItem(LabDto):
    market: str
    horizon_sessions: int
    resolved_count: int = Field(ge=0)
    nonresolved_count: int = Field(ge=0)
    mean_strategy_forward_return: Decimal | None = None
    mean_benchmark_forward_return: Decimal | None = None
    mean_excess_forward_return: Decimal | None = None


class LabBreakdownResponse(LabDto):
    experiment: LabExperimentItem
    action_breakdown: tuple[LabDecisionBreakdownItem, ...]
    regime_breakdown: tuple[LabDecisionBreakdownItem, ...]
    horizon_breakdown: tuple[LabDecisionBreakdownItem, ...]
    execution_attribution: tuple[LabExecutionBreakdownItem, ...]
    benchmark_horizon_breakdown: tuple[LabBenchmarkHorizonItem, ...]
    reason_codes: tuple[str, ...] = ()


class LabCompareRow(LabDto):
    experiment: LabExperimentItem
    sample_quality: str | None = None
    resolved_decision_count: int | None = None
    completed_trade_count: int | None = None
    win_rate: Decimal | None = None
    expectancy: Decimal | None = None
    profit_factor: Decimal | None = None
    average_episode_net_return: Decimal | None = None
    mean_benchmark_forward_return: Decimal | None = None
    mean_excess_forward_return: Decimal | None = None
    strategy_available: bool
    benchmark_available: bool
    reason_codes: tuple[str, ...] = ()


class LabCompareResponse(LabDto):
    selectors: tuple[str, ...]
    rows: tuple[LabCompareRow, ...]


__all__ = [name for name in globals() if name.startswith("Lab")]
