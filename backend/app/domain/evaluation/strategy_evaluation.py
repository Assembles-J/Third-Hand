"""Immutable N3.4 strategy-evaluation contracts and versioned aggregation policy."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field, field_validator, model_validator

from app.decision_semantics import FormalDecisionAction
from app.domain.evaluation.common import EvaluationContract, ExecutionDisposition


class SampleQualityState(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"
    LOW = "LOW"
    USABLE = "USABLE"
    STRONG = "STRONG"


class SampleQualityPolicy(EvaluationContract):
    policy_id: str
    version: str
    low_min_resolved_decisions: int = Field(ge=1)
    low_min_distinct_symbols: int = Field(ge=1)
    usable_min_resolved_decisions: int = Field(ge=1)
    usable_min_completed_episodes: int = Field(ge=0)
    usable_min_distinct_symbols: int = Field(ge=1)
    usable_max_nonresolved_ratio: Decimal = Field(ge=0, le=1)
    strong_min_resolved_decisions: int = Field(ge=1)
    strong_min_completed_episodes: int = Field(ge=0)
    strong_min_distinct_symbols: int = Field(ge=1)
    strong_max_nonresolved_ratio: Decimal = Field(ge=0, le=1)

    @field_validator("policy_id", "version")
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("sample-quality policy identity/version must not be blank")
        return normalized

    @model_validator(mode="after")
    def _ordered_thresholds(self) -> "SampleQualityPolicy":
        if self.usable_min_resolved_decisions < self.low_min_resolved_decisions:
            raise ValueError("usable decision threshold cannot be below low threshold")
        if self.strong_min_resolved_decisions < self.usable_min_resolved_decisions:
            raise ValueError("strong decision threshold cannot be below usable threshold")
        if self.strong_min_completed_episodes < self.usable_min_completed_episodes:
            raise ValueError("strong episode threshold cannot be below usable threshold")
        if self.usable_min_distinct_symbols < self.low_min_distinct_symbols:
            raise ValueError("usable symbol threshold cannot be below low threshold")
        if self.strong_min_distinct_symbols < self.usable_min_distinct_symbols:
            raise ValueError("strong symbol threshold cannot be below usable threshold")
        if self.strong_max_nonresolved_ratio > self.usable_max_nonresolved_ratio:
            raise ValueError("strong nonresolved ratio must be no looser than usable")
        return self

    def classify(
        self,
        *,
        resolved_decisions: int,
        completed_episodes: int,
        distinct_symbols: int,
        nonresolved_ratio: Decimal,
    ) -> SampleQualityState:
        if (
            resolved_decisions >= self.strong_min_resolved_decisions
            and completed_episodes >= self.strong_min_completed_episodes
            and distinct_symbols >= self.strong_min_distinct_symbols
            and nonresolved_ratio <= self.strong_max_nonresolved_ratio
        ):
            return SampleQualityState.STRONG
        if (
            resolved_decisions >= self.usable_min_resolved_decisions
            and completed_episodes >= self.usable_min_completed_episodes
            and distinct_symbols >= self.usable_min_distinct_symbols
            and nonresolved_ratio <= self.usable_max_nonresolved_ratio
        ):
            return SampleQualityState.USABLE
        if (
            resolved_decisions >= self.low_min_resolved_decisions
            and distinct_symbols >= self.low_min_distinct_symbols
        ):
            return SampleQualityState.LOW
        return SampleQualityState.INSUFFICIENT


class EvaluationPolicy(EvaluationContract):
    policy_id: str
    version: str
    decision_count_rule: str
    action_breakdown_rule: str
    regime_breakdown_rule: str
    episode_metric_rule: str
    portfolio_return_rule: str
    nonresolved_ratio_rule: str

    @field_validator(
        "policy_id",
        "version",
        "decision_count_rule",
        "action_breakdown_rule",
        "regime_breakdown_rule",
        "episode_metric_rule",
        "portfolio_return_rule",
        "nonresolved_ratio_rule",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("evaluation policy fields must not be blank")
        return normalized


class DecisionMetricBreakdown(EvaluationContract):
    action: FormalDecisionAction | None = None
    market_regime: str | None = None
    horizon_sessions: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    favorable_count: int = Field(ge=0)
    unfavorable_count: int = Field(ge=0)
    mixed_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    mean_forward_return: Decimal | None = None
    mean_mfe: Decimal | None = None
    mean_mae: Decimal | None = None

    @field_validator("market_regime")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def _counts_fit_sample(self) -> "DecisionMetricBreakdown":
        classified = (
            self.favorable_count
            + self.unfavorable_count
            + self.mixed_count
            + self.neutral_count
            + self.not_applicable_count
        )
        if classified != self.sample_count:
            raise ValueError("decision breakdown classification counts must equal sample_count")
        return self


class ExecutionDispositionCount(EvaluationContract):
    disposition: ExecutionDisposition
    count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    nonresolved_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _count_contract(self) -> "ExecutionDispositionCount":
        if self.resolved_count + self.nonresolved_count != self.count:
            raise ValueError("execution attribution counts must add up")
        return self


class StrategyEvaluation(EvaluationContract):
    evaluation_id: str
    experiment_id: str
    experiment_version: str
    universe_snapshot_id: str
    universe_snapshot_hash: str
    evaluation_policy_version: str
    sample_quality_policy_version: str
    outcome_policy_versions: tuple[str, ...]

    period_start: datetime | None = None
    period_end: datetime | None = None
    computed_at: datetime

    resolved_decision_count: int = Field(ge=0)
    decision_outcome_row_count: int = Field(ge=0)
    nonresolved_decision_outcome_count: int = Field(ge=0)
    completed_trade_count: int = Field(ge=0)
    distinct_symbol_count: int = Field(ge=0)
    sample_quality: SampleQualityState
    nonresolved_ratio: Decimal = Field(ge=0, le=1)

    total_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    turnover: Decimal | None = Field(default=None, ge=0)
    portfolio_metric_reason_codes: tuple[str, ...] = ()

    win_rate: Decimal | None = Field(default=None, ge=0, le=1)
    average_win: Decimal | None = None
    average_loss: Decimal | None = None
    payoff_ratio: Decimal | None = Field(default=None, ge=0)
    expectancy: Decimal | None = None
    profit_factor: Decimal | None = Field(default=None, ge=0)
    max_consecutive_losses: int = Field(ge=0)

    average_holding_sessions: Decimal | None = Field(default=None, ge=0)
    total_fees: Decimal = Field(ge=0)
    total_slippage: Decimal | None = None
    average_episode_net_return: Decimal | None = None
    average_episode_mfe: Decimal | None = None
    average_episode_mae: Decimal | None = None
    worst_episode_drawdown: Decimal | None = None

    action_breakdown: tuple[DecisionMetricBreakdown, ...] = ()
    regime_breakdown: tuple[DecisionMetricBreakdown, ...] = ()
    horizon_breakdown: tuple[DecisionMetricBreakdown, ...] = ()
    execution_attribution: tuple[ExecutionDispositionCount, ...] = ()

    source_hash: str

    @field_validator(
        "evaluation_id",
        "experiment_id",
        "experiment_version",
        "universe_snapshot_id",
        "evaluation_policy_version",
        "sample_quality_policy_version",
        "source_hash",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("strategy evaluation identity/version fields must not be blank")
        return normalized

    @field_validator("universe_snapshot_hash")
    @classmethod
    def _universe_hash(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("universe_snapshot_hash must be a sha256 hex digest")
        return normalized

    @field_validator("computed_at", "period_start", "period_end")
    @classmethod
    def _aware_times(cls, value: datetime | None, info):
        if value is not None and value.tzinfo is None:
            raise ValueError(f"{info.field_name} must include timezone information")
        return value

    @model_validator(mode="after")
    def _evaluation_contract(self) -> "StrategyEvaluation":
        if self.period_start is not None and self.period_end is not None and self.period_end < self.period_start:
            raise ValueError("period_end cannot be earlier than period_start")
        portfolio_values = (self.total_return, self.max_drawdown, self.turnover)
        if any(value is None for value in portfolio_values) and not self.portfolio_metric_reason_codes:
            raise ValueError("unavailable portfolio metrics require reason codes")
        if all(value is not None for value in portfolio_values) and self.portfolio_metric_reason_codes:
            raise ValueError("available portfolio metrics must not carry unavailable reason codes")
        if self.completed_trade_count == 0:
            economic_values = (
                self.win_rate,
                self.average_win,
                self.average_loss,
                self.payoff_ratio,
                self.expectancy,
                self.profit_factor,
                self.average_holding_sessions,
                self.average_episode_net_return,
                self.average_episode_mfe,
                self.average_episode_mae,
                self.worst_episode_drawdown,
            )
            if any(value is not None for value in economic_values):
                raise ValueError("no completed trades means episode-economic metrics must be absent")
        return self


def swing_v1_sample_quality_policy() -> SampleQualityPolicy:
    """Versioned sufficiency heuristic; it is not a statement of strategy quality."""
    return SampleQualityPolicy(
        policy_id="swing-v1-sample-quality",
        version="1.0.0",
        low_min_resolved_decisions=10,
        low_min_distinct_symbols=3,
        usable_min_resolved_decisions=30,
        usable_min_completed_episodes=10,
        usable_min_distinct_symbols=8,
        usable_max_nonresolved_ratio=Decimal("0.20"),
        strong_min_resolved_decisions=100,
        strong_min_completed_episodes=30,
        strong_min_distinct_symbols=20,
        strong_max_nonresolved_ratio=Decimal("0.10"),
    )


def swing_v1_evaluation_policy() -> EvaluationPolicy:
    return EvaluationPolicy(
        policy_id="swing-v1-evaluation",
        version="1.0.0",
        decision_count_rule="unique_decision_with_any_resolved_horizon_v1",
        action_breakdown_rule="action_and_horizon_resolved_rows_v1",
        regime_breakdown_rule="regime_and_horizon_resolved_rows_v1",
        episode_metric_rule="closed_episode_net_return_and_realized_pnl_v1",
        portfolio_return_rule="require_experiment_equity_curve_no_episode_compound_proxy_v1",
        nonresolved_ratio_rule="terminal_decision_outcome_rows_v1",
    )


__all__ = [
    "DecisionMetricBreakdown",
    "EvaluationPolicy",
    "ExecutionDispositionCount",
    "SampleQualityPolicy",
    "SampleQualityState",
    "StrategyEvaluation",
    "swing_v1_evaluation_policy",
    "swing_v1_sample_quality_policy",
]
