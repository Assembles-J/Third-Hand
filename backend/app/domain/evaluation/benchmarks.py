"""Immutable N3.5 benchmark contracts.

Benchmarking is a read/measurement concern. These models never select a Formal
Action, refresh a provider, change Personal Universe membership, or write paper
trading state.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field, field_validator, model_validator

from app.domain.evaluation.common import EvaluationContract, OutcomeStatus


class BenchmarkType(str, Enum):
    MARKET_INDEX = "MARKET_INDEX"
    BUY_AND_HOLD_SYMBOL = "BUY_AND_HOLD_SYMBOL"
    EQUAL_WEIGHT_ELIGIBLE_UNIVERSE = "EQUAL_WEIGHT_ELIGIBLE_UNIVERSE"
    FORMAL_SWING_V1 = "FORMAL_SWING_V1"
    NEUTRAL_DIAGNOSTIC = "NEUTRAL_DIAGNOSTIC"


class BenchmarkConstituentSource(str, Enum):
    EXPLICIT_SYMBOL = "EXPLICIT_SYMBOL"
    EXPERIMENT_UNIVERSE = "EXPERIMENT_UNIVERSE"
    REFERENCE_EXPERIMENT = "REFERENCE_EXPERIMENT"
    NONE = "NONE"


class BenchmarkPolicy(EvaluationContract):
    benchmark_policy_id: str
    version: str
    benchmark_type: BenchmarkType
    constituent_source: BenchmarkConstituentSource

    benchmark_market: str | None = None
    benchmark_symbol: str | None = None
    reference_experiment_id: str | None = None
    reference_experiment_version: str | None = None

    alignment_rule: str = "prior_completed_session_close_to_outcome_end_v1"
    missing_data_rule: str = "strict_no_partial_constituent_average_v1"
    corporate_action_adjustment_rule: str = "point_in_time_adjusted_price_series_v1"
    cost_assumption_bps: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator(
        "benchmark_policy_id",
        "version",
        "alignment_rule",
        "missing_data_rule",
        "corporate_action_adjustment_rule",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("benchmark policy fields must not be blank")
        return normalized

    @field_validator("benchmark_market")
    @classmethod
    def _market(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        aliases = {"CN_A": "CN", "A": "CN", "MAINLAND": "CN"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"CN", "HK", "US"}:
            raise ValueError("benchmark_market must be CN, HK, or US")
        return normalized

    @field_validator("benchmark_symbol")
    @classmethod
    def _symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized or None

    @field_validator("reference_experiment_id", "reference_experiment_version")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def _type_contract(self) -> "BenchmarkPolicy":
        explicit = {BenchmarkType.MARKET_INDEX, BenchmarkType.BUY_AND_HOLD_SYMBOL}
        if self.benchmark_type in explicit:
            if self.constituent_source != BenchmarkConstituentSource.EXPLICIT_SYMBOL:
                raise ValueError("explicit symbol benchmark requires EXPLICIT_SYMBOL source")
            if not self.benchmark_market or not self.benchmark_symbol:
                raise ValueError("explicit symbol benchmark requires benchmark_market and benchmark_symbol")
            if self.reference_experiment_id or self.reference_experiment_version:
                raise ValueError("explicit symbol benchmark must not carry reference experiment")
        elif self.benchmark_type == BenchmarkType.EQUAL_WEIGHT_ELIGIBLE_UNIVERSE:
            if self.constituent_source != BenchmarkConstituentSource.EXPERIMENT_UNIVERSE:
                raise ValueError("equal-weight benchmark requires EXPERIMENT_UNIVERSE source")
            if self.benchmark_market or self.benchmark_symbol:
                raise ValueError("equal-weight experiment benchmark must not pin one benchmark symbol")
            if self.reference_experiment_id or self.reference_experiment_version:
                raise ValueError("equal-weight benchmark must not carry reference experiment")
        elif self.benchmark_type == BenchmarkType.FORMAL_SWING_V1:
            if self.constituent_source != BenchmarkConstituentSource.REFERENCE_EXPERIMENT:
                raise ValueError("formal strategy benchmark requires REFERENCE_EXPERIMENT source")
            if not self.reference_experiment_id or not self.reference_experiment_version:
                raise ValueError("formal strategy benchmark requires reference experiment id/version")
            if self.benchmark_market or self.benchmark_symbol:
                raise ValueError("formal strategy benchmark must not carry market symbol")
        elif self.benchmark_type == BenchmarkType.NEUTRAL_DIAGNOSTIC:
            if self.constituent_source != BenchmarkConstituentSource.NONE:
                raise ValueError("neutral diagnostic benchmark requires NONE source")
            if any(
                value is not None
                for value in (
                    self.benchmark_market,
                    self.benchmark_symbol,
                    self.reference_experiment_id,
                    self.reference_experiment_version,
                )
            ):
                raise ValueError("neutral diagnostic benchmark must not carry constituents")
        return self


class BenchmarkObservation(EvaluationContract):
    benchmark_observation_id: str
    experiment_id: str
    experiment_version: str
    universe_snapshot_id: str
    universe_snapshot_hash: str
    benchmark_policy_id: str
    benchmark_policy_version: str
    benchmark_type: BenchmarkType

    decision_outcome_id: str
    decision_id: str
    strategy_symbol: str
    market: str
    horizon_sessions: int = Field(ge=1)
    decision_time: datetime
    observation_end: datetime
    reference_session: str | None = None
    end_session: str | None = None

    outcome_status: OutcomeStatus
    strategy_forward_return: Decimal | None = None
    benchmark_forward_return: Decimal | None = None
    excess_forward_return: Decimal | None = None
    constituent_count: int = Field(default=0, ge=0)
    constituent_hash: str | None = None
    reason_codes: tuple[str, ...] = ()
    source_lineage_hash: str | None = None
    resolved_at: datetime | None = None

    @field_validator(
        "benchmark_observation_id",
        "experiment_id",
        "experiment_version",
        "universe_snapshot_id",
        "benchmark_policy_id",
        "benchmark_policy_version",
        "decision_outcome_id",
        "decision_id",
        "strategy_symbol",
        "market",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("benchmark observation identity fields must not be blank")
        return normalized

    @field_validator("universe_snapshot_hash", "constituent_hash", "source_lineage_hash")
    @classmethod
    def _hashes(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError(f"{info.field_name} must be a sha256 hex digest")
        return normalized

    @field_validator("decision_time", "observation_end", "resolved_at")
    @classmethod
    def _aware_times(cls, value: datetime | None, info):
        if value is not None and value.tzinfo is None:
            raise ValueError(f"{info.field_name} must include timezone information")
        return value

    @model_validator(mode="after")
    def _status_contract(self) -> "BenchmarkObservation":
        metrics = (
            self.strategy_forward_return,
            self.benchmark_forward_return,
            self.excess_forward_return,
        )
        if self.observation_end < self.decision_time:
            raise ValueError("benchmark observation_end cannot precede decision_time")
        if self.outcome_status == OutcomeStatus.PENDING:
            if any(value is not None for value in metrics):
                raise ValueError("PENDING benchmark observation cannot carry metrics")
            if self.resolved_at is not None or self.source_lineage_hash is not None:
                raise ValueError("PENDING benchmark observation cannot claim terminal lineage")
            return self
        if self.resolved_at is None or not self.source_lineage_hash:
            raise ValueError("terminal benchmark observation requires resolved_at and lineage")
        if self.outcome_status == OutcomeStatus.RESOLVED:
            if any(value is None for value in metrics):
                raise ValueError("RESOLVED benchmark observation requires all return metrics")
            if not self.reference_session or not self.end_session:
                raise ValueError("RESOLVED benchmark observation requires aligned sessions")
            if self.excess_forward_return != self.strategy_forward_return - self.benchmark_forward_return:
                raise ValueError("excess_forward_return must equal strategy minus benchmark")
            if self.benchmark_type != BenchmarkType.NEUTRAL_DIAGNOSTIC:
                if self.constituent_count <= 0 or not self.constituent_hash:
                    raise ValueError("resolved market benchmark requires constituent lineage")
        else:
            if any(value is not None for value in metrics):
                raise ValueError("invalid/insufficient benchmark observation cannot carry metrics")
            if not self.reason_codes:
                raise ValueError("invalid/insufficient benchmark observation requires reason codes")
        return self


class BenchmarkHorizonSummary(EvaluationContract):
    market: str
    horizon_sessions: int = Field(ge=1)
    resolved_count: int = Field(ge=0)
    nonresolved_count: int = Field(ge=0)
    mean_strategy_forward_return: Decimal | None = None
    mean_benchmark_forward_return: Decimal | None = None
    mean_excess_forward_return: Decimal | None = None

    @model_validator(mode="after")
    def _metrics_follow_count(self) -> "BenchmarkHorizonSummary":
        metrics = (
            self.mean_strategy_forward_return,
            self.mean_benchmark_forward_return,
            self.mean_excess_forward_return,
        )
        if self.resolved_count == 0 and any(value is not None for value in metrics):
            raise ValueError("empty benchmark summary cannot carry means")
        if self.resolved_count > 0 and any(value is None for value in metrics):
            raise ValueError("resolved benchmark summary requires all means")
        return self


class BenchmarkEvaluation(EvaluationContract):
    benchmark_evaluation_id: str
    experiment_id: str
    experiment_version: str
    universe_snapshot_id: str
    universe_snapshot_hash: str
    benchmark_policy_id: str
    benchmark_policy_version: str
    benchmark_type: BenchmarkType
    computed_at: datetime

    resolved_observation_count: int = Field(ge=0)
    nonresolved_observation_count: int = Field(ge=0)
    mean_strategy_forward_return: Decimal | None = None
    mean_benchmark_forward_return: Decimal | None = None
    mean_excess_forward_return: Decimal | None = None
    horizon_breakdown: tuple[BenchmarkHorizonSummary, ...] = ()

    portfolio_benchmark_return: Decimal | None = None
    portfolio_excess_return: Decimal | None = None
    portfolio_metric_reason_codes: tuple[str, ...] = ()
    source_hash: str

    @field_validator(
        "benchmark_evaluation_id",
        "experiment_id",
        "experiment_version",
        "universe_snapshot_id",
        "benchmark_policy_id",
        "benchmark_policy_version",
        "source_hash",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("benchmark evaluation identity fields must not be blank")
        return normalized

    @field_validator("universe_snapshot_hash", "source_hash")
    @classmethod
    def _sha256(cls, value: str, info) -> str:
        normalized = str(value or "").strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError(f"{info.field_name} must be a sha256 hex digest")
        return normalized

    @field_validator("computed_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("benchmark computed_at must include timezone information")
        return value

    @model_validator(mode="after")
    def _evaluation_contract(self) -> "BenchmarkEvaluation":
        means = (
            self.mean_strategy_forward_return,
            self.mean_benchmark_forward_return,
            self.mean_excess_forward_return,
        )
        if self.resolved_observation_count == 0 and any(value is not None for value in means):
            raise ValueError("benchmark evaluation with no resolved observations cannot carry means")
        if self.resolved_observation_count > 0 and any(value is None for value in means):
            raise ValueError("resolved benchmark evaluation requires aggregate means")
        if self.portfolio_benchmark_return is None or self.portfolio_excess_return is None:
            if not self.portfolio_metric_reason_codes:
                raise ValueError("unavailable portfolio benchmark metrics require reason codes")
        elif self.portfolio_metric_reason_codes:
            raise ValueError("available portfolio benchmark metrics must not carry unavailable reasons")
        return self


__all__ = [
    "BenchmarkConstituentSource",
    "BenchmarkEvaluation",
    "BenchmarkHorizonSummary",
    "BenchmarkObservation",
    "BenchmarkPolicy",
    "BenchmarkType",
]
