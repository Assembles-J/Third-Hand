"""Immutable N3 outcome contracts.

This module defines what a resolved observation must look like. It intentionally
contains no price lookup, trading-calendar traversal, scoring algorithm, or
paper-execution side effect; those belong to later N3 slices.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from app.decision_semantics import FormalDecisionAction
from app.domain.evaluation.common import (
    ActionOutcomeClass,
    EvaluationContract,
    ExecutionDisposition,
    OutcomeStatus,
)


def _timezone_required(value: datetime | None, label: str) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{label} must include timezone information")
    return value


def _finite_decimal(value: Decimal | None, label: str) -> Decimal | None:
    if value is not None and not value.is_finite():
        raise ValueError(f"{label} must be finite")
    return value


class DecisionOutcome(EvaluationContract):
    outcome_id: str
    experiment_id: str
    experiment_version: str
    decision_id: str
    symbol: str
    market: str
    action: FormalDecisionAction
    decision_time: datetime
    reference_price: Decimal | None = Field(default=None, gt=0)

    horizon_sessions: int = Field(ge=1)
    observation_end: datetime
    outcome_status: OutcomeStatus

    forward_return: Decimal | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None
    target_hit: bool | None = None
    stop_hit: bool | None = None
    target_before_stop: bool | None = None

    market_regime: str | None = None
    action_outcome_class: ActionOutcomeClass | None = None
    outcome_reason_codes: tuple[str, ...] = ()

    source_lineage_hash: str | None = None
    outcome_policy_version: str
    resolved_at: datetime | None = None

    @field_validator(
        "outcome_id",
        "experiment_id",
        "experiment_version",
        "decision_id",
        "symbol",
        "market",
        "outcome_policy_version",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("decision outcome identity fields must not be blank")
        return normalized

    @field_validator("market_regime", "source_lineage_hash")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("decision_time", "observation_end", "resolved_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None, info):
        return _timezone_required(value, info.field_name)

    @field_validator("reference_price", "forward_return", "mfe", "mae")
    @classmethod
    def _finite_numbers(cls, value: Decimal | None, info):
        return _finite_decimal(value, info.field_name)

    @field_validator("mfe")
    @classmethod
    def _mfe_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("mfe must be >= 0")
        return value

    @field_validator("mae")
    @classmethod
    def _mae_non_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value > 0:
            raise ValueError("mae must be <= 0")
        return value

    @model_validator(mode="after")
    def _status_contract(self) -> "DecisionOutcome":
        if self.observation_end < self.decision_time:
            raise ValueError("observation_end must not be earlier than decision_time")

        score_fields = (
            self.forward_return,
            self.mfe,
            self.mae,
            self.target_hit,
            self.stop_hit,
            self.target_before_stop,
            self.action_outcome_class,
        )
        terminal = self.outcome_status in {
            OutcomeStatus.RESOLVED,
            OutcomeStatus.INSUFFICIENT_DATA,
            OutcomeStatus.INVALID,
        }

        if self.outcome_status == OutcomeStatus.PENDING:
            if self.reference_price is None:
                raise ValueError("PENDING decision outcomes require reference_price")
            if any(value is not None for value in score_fields):
                raise ValueError("PENDING decision outcomes must not carry resolved metrics")
            if self.resolved_at is not None or self.source_lineage_hash is not None:
                raise ValueError("PENDING decision outcomes must not claim terminal lineage")
            return self

        if terminal and (self.resolved_at is None or not self.source_lineage_hash):
            raise ValueError("terminal decision outcomes require resolved_at and source_lineage_hash")

        if self.outcome_status == OutcomeStatus.RESOLVED:
            if self.reference_price is None:
                raise ValueError("RESOLVED decision outcomes require reference_price")
            required = {
                "forward_return": self.forward_return,
                "mfe": self.mfe,
                "mae": self.mae,
                "action_outcome_class": self.action_outcome_class,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(f"RESOLVED decision outcome missing metrics: {', '.join(missing)}")
            if self.resolved_at is not None and self.resolved_at < self.observation_end:
                raise ValueError("resolved_at must not precede observation_end")
        else:
            if any(value is not None for value in score_fields):
                raise ValueError(
                    "INSUFFICIENT_DATA/INVALID decision outcomes must not carry score metrics"
                )
            if not self.outcome_reason_codes:
                raise ValueError("non-resolved terminal outcomes require reason codes")

        if self.target_before_stop is not None and (
            self.target_hit is None or self.stop_hit is None
        ):
            raise ValueError("target_before_stop requires explicit target_hit and stop_hit facts")

        return self


class ExecutionOutcome(EvaluationContract):
    execution_outcome_id: str
    experiment_id: str
    experiment_version: str
    decision_id: str
    requested_action: FormalDecisionAction
    outcome_status: OutcomeStatus
    execution_disposition: ExecutionDisposition
    execution_reason_codes: tuple[str, ...] = ()

    requested_quantity: Decimal | None = Field(default=None, ge=0)
    max_executable_quantity: Decimal | None = Field(default=None, ge=0)
    executed_quantity: Decimal | None = Field(default=None, ge=0)

    observed_quote_at: datetime | None = None
    market_session_status: str | None = None
    deferral_id: str | None = None
    fill_ids: tuple[str, ...] = ()
    resolved_at: datetime | None = None
    source_lineage_hash: str | None = None

    @field_validator(
        "execution_outcome_id", "experiment_id", "experiment_version", "decision_id"
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("execution outcome identity fields must not be blank")
        return normalized

    @field_validator("market_session_status", "deferral_id", "source_lineage_hash")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("observed_quote_at", "resolved_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None, info):
        return _timezone_required(value, info.field_name)

    @field_validator("requested_quantity", "max_executable_quantity", "executed_quantity")
    @classmethod
    def _finite_quantities(cls, value: Decimal | None, info):
        return _finite_decimal(value, info.field_name)

    @model_validator(mode="after")
    def _execution_contract(self) -> "ExecutionOutcome":
        non_executable_actions = {"WAIT", "HOLD", "BLOCKED"}

        if self.outcome_status == OutcomeStatus.PENDING:
            if self.execution_disposition != ExecutionDisposition.PENDING:
                raise ValueError("PENDING execution outcome requires PENDING disposition")
            if self.resolved_at is not None or self.source_lineage_hash is not None:
                raise ValueError("PENDING execution outcome must not claim terminal lineage")
            if self.fill_ids or (self.executed_quantity not in (None, Decimal("0"))):
                raise ValueError("PENDING execution outcome cannot contain fills")
            return self

        if self.resolved_at is None or not self.source_lineage_hash:
            raise ValueError("terminal execution outcomes require resolved_at and source_lineage_hash")

        if self.outcome_status in {OutcomeStatus.INSUFFICIENT_DATA, OutcomeStatus.INVALID}:
            if not self.execution_reason_codes:
                raise ValueError("non-resolved terminal execution outcomes require reason codes")
            if self.fill_ids or (self.executed_quantity not in (None, Decimal("0"))):
                raise ValueError("invalid/insufficient execution outcomes cannot claim fills")
            return self

        if self.requested_action in non_executable_actions:
            if self.execution_disposition != ExecutionDisposition.NOT_APPLICABLE:
                raise ValueError("WAIT/HOLD/BLOCKED execution disposition must be NOT_APPLICABLE")
            if any(
                value not in (None, Decimal("0"))
                for value in (
                    self.requested_quantity,
                    self.max_executable_quantity,
                    self.executed_quantity,
                )
            ):
                raise ValueError("non-executable Formal Actions must not carry execution quantities")
            if self.fill_ids or self.deferral_id:
                raise ValueError("non-executable Formal Actions must not carry fill/deferral links")
            return self

        if self.execution_disposition == ExecutionDisposition.NOT_APPLICABLE:
            raise ValueError("BUY/ADD/REDUCE/EXIT cannot be NOT_APPLICABLE")

        if self.executed_quantity is not None and self.max_executable_quantity is not None:
            if self.executed_quantity > self.max_executable_quantity:
                raise ValueError("executed_quantity cannot exceed max_executable_quantity")
        if self.executed_quantity is not None and self.requested_quantity is not None:
            if self.executed_quantity > self.requested_quantity:
                raise ValueError("executed_quantity cannot exceed requested_quantity")

        if self.execution_disposition == ExecutionDisposition.EXECUTED:
            if self.executed_quantity is None or self.executed_quantity <= 0 or not self.fill_ids:
                raise ValueError("EXECUTED disposition requires positive executed_quantity and fill_ids")
        elif self.execution_disposition == ExecutionDisposition.PARTIALLY_EXECUTED:
            if (
                self.requested_quantity is None
                or self.executed_quantity is None
                or self.executed_quantity <= 0
                or self.executed_quantity >= self.requested_quantity
                or not self.fill_ids
            ):
                raise ValueError(
                    "PARTIALLY_EXECUTED requires 0 < executed_quantity < requested_quantity and fill_ids"
                )
        elif self.execution_disposition in {
            ExecutionDisposition.BLOCKED,
            ExecutionDisposition.DEFERRED,
            ExecutionDisposition.EXPIRED,
        }:
            if self.fill_ids or (self.executed_quantity not in (None, Decimal("0"))):
                raise ValueError("blocked/deferred/expired execution cannot claim fills")
            if not self.execution_reason_codes:
                raise ValueError("blocked/deferred/expired execution requires reason codes")
            if (
                self.execution_disposition == ExecutionDisposition.DEFERRED
                and not self.deferral_id
            ):
                raise ValueError("DEFERRED execution requires deferral_id")
        elif self.execution_disposition == ExecutionDisposition.PENDING:
            raise ValueError("RESOLVED execution outcome cannot keep PENDING disposition")

        return self


class TradeEpisodeOutcome(EvaluationContract):
    episode_outcome_id: str
    experiment_id: str
    experiment_version: str
    position_episode_id: str
    symbol: str
    outcome_status: OutcomeStatus

    opened_at: datetime
    closed_at: datetime | None = None
    holding_sessions: int | None = Field(default=None, ge=0)

    gross_return: Decimal | None = None
    net_return: Decimal | None = None
    realized_pnl: Decimal | None = None
    fees: Decimal | None = Field(default=None, ge=0)
    slippage: Decimal | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None
    episode_max_drawdown: Decimal | None = None

    entry_decision_ids: tuple[str, ...] = ()
    position_decision_ids: tuple[str, ...] = ()
    fill_ids: tuple[str, ...] = ()

    outcome_policy_version: str
    outcome_reason_codes: tuple[str, ...] = ()
    source_lineage_hash: str | None = None
    resolved_at: datetime | None = None

    @field_validator(
        "episode_outcome_id",
        "experiment_id",
        "experiment_version",
        "position_episode_id",
        "symbol",
        "outcome_policy_version",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("episode outcome identity fields must not be blank")
        return normalized

    @field_validator("source_lineage_hash")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("opened_at", "closed_at", "resolved_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None, info):
        return _timezone_required(value, info.field_name)

    @field_validator(
        "gross_return",
        "net_return",
        "realized_pnl",
        "fees",
        "slippage",
        "mfe",
        "mae",
        "episode_max_drawdown",
    )
    @classmethod
    def _finite_numbers(cls, value: Decimal | None, info):
        return _finite_decimal(value, info.field_name)

    @field_validator("mfe")
    @classmethod
    def _mfe_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("mfe must be >= 0")
        return value

    @field_validator("mae", "episode_max_drawdown")
    @classmethod
    def _drawdowns_non_positive(cls, value: Decimal | None, info) -> Decimal | None:
        if value is not None and value > 0:
            raise ValueError(f"{info.field_name} must be <= 0")
        return value

    @model_validator(mode="after")
    def _episode_contract(self) -> "TradeEpisodeOutcome":
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError("closed_at must not be earlier than opened_at")

        economic_fields = (
            self.holding_sessions,
            self.gross_return,
            self.net_return,
            self.realized_pnl,
            self.fees,
            self.slippage,
            self.mfe,
            self.mae,
            self.episode_max_drawdown,
        )

        if self.outcome_status == OutcomeStatus.PENDING:
            if self.closed_at is not None:
                raise ValueError("PENDING episode must not be marked closed")
            if any(value is not None for value in economic_fields):
                raise ValueError("PENDING episode must not carry terminal economic metrics")
            if self.resolved_at is not None or self.source_lineage_hash is not None:
                raise ValueError("PENDING episode must not claim terminal lineage")
            return self

        if self.resolved_at is None or not self.source_lineage_hash:
            raise ValueError("terminal episode outcomes require resolved_at and source_lineage_hash")

        if self.outcome_status == OutcomeStatus.RESOLVED:
            required = {
                "closed_at": self.closed_at,
                "holding_sessions": self.holding_sessions,
                "gross_return": self.gross_return,
                "net_return": self.net_return,
                "realized_pnl": self.realized_pnl,
                "fees": self.fees,
                "slippage": self.slippage,
                "mfe": self.mfe,
                "mae": self.mae,
                "episode_max_drawdown": self.episode_max_drawdown,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(f"RESOLVED episode outcome missing metrics: {', '.join(missing)}")
            if not self.fill_ids:
                raise ValueError("RESOLVED trade episode requires fill_ids")
            if self.closed_at is not None and self.resolved_at < self.closed_at:
                raise ValueError("resolved_at must not precede closed_at")
        else:
            if any(value is not None for value in economic_fields):
                raise ValueError("INVALID/INSUFFICIENT_DATA episode must not carry economic metrics")
            if not self.outcome_reason_codes:
                raise ValueError("non-resolved terminal episode requires reason codes")

        return self


__all__ = ["DecisionOutcome", "ExecutionOutcome", "TradeEpisodeOutcome"]
