"""Versioned N3 outcome-policy contracts.

Policies define what may be measured later by OutcomeResolver. They contain no
market-data lookup and no trading authority.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from app.decision_semantics import FormalDecisionAction
from app.domain.evaluation.common import ActionOutcomeDimension, EvaluationContract


_FORMAL_ACTIONS: tuple[FormalDecisionAction, ...] = (
    "BUY",
    "WAIT",
    "HOLD",
    "ADD",
    "REDUCE",
    "EXIT",
    "BLOCKED",
)


class ActionOutcomeRule(EvaluationContract):
    action: FormalDecisionAction
    dimensions: tuple[ActionOutcomeDimension, ...]

    @field_validator("dimensions")
    @classmethod
    def _dimensions_non_empty_unique(
        cls,
        value: tuple[ActionOutcomeDimension, ...],
    ) -> tuple[ActionOutcomeDimension, ...]:
        if not value:
            raise ValueError("action outcome rule requires at least one dimension")
        if len(value) != len(set(value)):
            raise ValueError("action outcome dimensions must be unique")
        return value


class ActionOutcomePolicy(EvaluationContract):
    policy_id: str
    version: str
    rules: tuple[ActionOutcomeRule, ...]

    @field_validator("policy_id", "version")
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("policy identity/version must not be blank")
        return normalized

    @model_validator(mode="after")
    def _all_actions_explicit(self) -> "ActionOutcomePolicy":
        actions = tuple(rule.action for rule in self.rules)
        if len(actions) != len(set(actions)):
            raise ValueError("action outcome policy contains duplicate actions")
        missing = [action for action in _FORMAL_ACTIONS if action not in actions]
        extra = [action for action in actions if action not in _FORMAL_ACTIONS]
        if missing or extra:
            raise ValueError(
                "action outcome policy must define every Formal Action exactly once; "
                f"missing={missing}, extra={extra}"
            )
        return self

    def rule_for(self, action: FormalDecisionAction) -> ActionOutcomeRule:
        return next(rule for rule in self.rules if rule.action == action)


class TargetStopRule(EvaluationContract):
    """Optional target/stop event definition used only when explicitly configured."""

    action: FormalDecisionAction
    horizon_sessions: int = Field(ge=1)
    target_return: Decimal = Field(gt=0)
    stop_return: Decimal = Field(lt=0)


class OutcomePolicy(EvaluationContract):
    policy_id: str
    version: str
    decision_horizons: tuple[int, ...]
    action_outcome_policy_id: str
    action_outcome_policy_version: str
    target_stop_rules: tuple[TargetStopRule, ...] = ()
    benchmark_alignment_rule: str
    trading_calendar_rule: str
    missing_data_rule: str
    suspended_symbol_rule: str
    corporate_action_adjustment_rule: str

    @field_validator(
        "policy_id",
        "version",
        "action_outcome_policy_id",
        "action_outcome_policy_version",
        "benchmark_alignment_rule",
        "trading_calendar_rule",
        "missing_data_rule",
        "suspended_symbol_rule",
        "corporate_action_adjustment_rule",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("outcome policy fields must not be blank")
        return normalized

    @field_validator("decision_horizons")
    @classmethod
    def _horizons_positive_sorted_unique(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            raise ValueError("decision_horizons must not be empty")
        normalized = tuple(int(item) for item in value)
        if any(item <= 0 for item in normalized):
            raise ValueError("decision horizons must be positive trading-session counts")
        if normalized != tuple(sorted(set(normalized))):
            raise ValueError("decision horizons must be sorted and unique")
        return normalized

    @model_validator(mode="after")
    def _target_stop_keys_unique(self) -> "OutcomePolicy":
        keys = [(rule.action, rule.horizon_sessions) for rule in self.target_stop_rules]
        if len(keys) != len(set(keys)):
            raise ValueError("target/stop rules must be unique by action and horizon")
        unknown_horizons = sorted(
            {rule.horizon_sessions for rule in self.target_stop_rules}
            - set(self.decision_horizons)
        )
        if unknown_horizons:
            raise ValueError(
                f"target/stop rule horizons are not part of decision_horizons: {unknown_horizons}"
            )
        return self


def swing_v1_action_outcome_policy() -> ActionOutcomePolicy:
    """Initial action-specific questions for Formal SWING_V1 evaluation."""

    return ActionOutcomePolicy(
        policy_id="swing-v1-action-outcome",
        version="1.0.0",
        rules=(
            ActionOutcomeRule(
                action="BUY",
                dimensions=(
                    ActionOutcomeDimension.ENTRY_QUALITY,
                    ActionOutcomeDimension.FORWARD_RETURN,
                    ActionOutcomeDimension.MFE_MAE,
                    ActionOutcomeDimension.TARGET_BEFORE_STOP,
                ),
            ),
            ActionOutcomeRule(
                action="WAIT",
                dimensions=(
                    ActionOutcomeDimension.AVOIDED_LOSS,
                    ActionOutcomeDimension.MISSED_OPPORTUNITY,
                    ActionOutcomeDimension.LATER_ENTRY_AVAILABILITY,
                ),
            ),
            ActionOutcomeRule(
                action="HOLD",
                dimensions=(
                    ActionOutcomeDimension.CONTINUATION_QUALITY,
                    ActionOutcomeDimension.FORWARD_RETURN,
                    ActionOutcomeDimension.MFE_MAE,
                ),
            ),
            ActionOutcomeRule(
                action="ADD",
                dimensions=(
                    ActionOutcomeDimension.ENTRY_QUALITY,
                    ActionOutcomeDimension.FORWARD_RETURN,
                    ActionOutcomeDimension.MFE_MAE,
                    ActionOutcomeDimension.TARGET_BEFORE_STOP,
                ),
            ),
            ActionOutcomeRule(
                action="REDUCE",
                dimensions=(
                    ActionOutcomeDimension.RISK_REDUCTION_QUALITY,
                    ActionOutcomeDimension.AVOIDED_DOWNSIDE,
                    ActionOutcomeDimension.OPPORTUNITY_COST,
                ),
            ),
            ActionOutcomeRule(
                action="EXIT",
                dimensions=(
                    ActionOutcomeDimension.EXIT_QUALITY,
                    ActionOutcomeDimension.AVOIDED_DOWNSIDE,
                    ActionOutcomeDimension.PREMATURE_EXIT_OPPORTUNITY_COST,
                ),
            ),
            ActionOutcomeRule(
                action="BLOCKED",
                dimensions=(
                    ActionOutcomeDimension.GATE_CORRECTNESS,
                    ActionOutcomeDimension.DATA_QUALITY_ATTRIBUTION,
                ),
            ),
        ),
    )


def swing_v1_outcome_policy() -> OutcomePolicy:
    """Initial observation contract; target/stop thresholds remain unconfigured.

    N3.2 deliberately does not invent target/stop percentages. When a later
    strategy/evaluation change introduces them, it must create a new policy
    version instead of rewriting this one.
    """

    action_policy = swing_v1_action_outcome_policy()
    return OutcomePolicy(
        policy_id="swing-v1-outcome",
        version="1.0.0",
        decision_horizons=(3, 5, 10, 20),
        action_outcome_policy_id=action_policy.policy_id,
        action_outcome_policy_version=action_policy.version,
        target_stop_rules=(),
        benchmark_alignment_rule="same_market_same_trading_window",
        trading_calendar_rule="instrument_market_calendar_v1",
        missing_data_rule="terminal_insufficient_data_excluded_from_resolved_metrics",
        suspended_symbol_rule="count_market_sessions_only_when_observable_v1",
        corporate_action_adjustment_rule="point_in_time_adjusted_price_series_v1",
    )


__all__ = [
    "ActionOutcomePolicy",
    "ActionOutcomeRule",
    "OutcomePolicy",
    "TargetStopRule",
    "swing_v1_action_outcome_policy",
    "swing_v1_outcome_policy",
]
