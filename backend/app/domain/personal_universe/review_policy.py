"""Deterministic PUX2 review permission contracts.

Review permission is deliberately separate from scheduler cadence and trading
authority.  The policy can permit analysis depth; it cannot manufacture a
Formal Action or bypass Risk/Execution policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


REVIEW_POLICY_VERSION = "PUX2_REVIEW_V1"


class ReviewMode(StrEnum):
    NO_REVIEW = "NO_REVIEW"
    GUARD_ONLY = "GUARD_ONLY"
    POSITION_REVIEW = "POSITION_REVIEW"
    FULL_RESEARCH = "FULL_RESEARCH"


class AnalysisDepth(StrEnum):
    NONE = "NONE"
    GUARDS = "GUARDS"
    POSITION = "POSITION"
    FULL = "FULL"


@dataclass(frozen=True)
class ReviewPolicyInput:
    symbol: str
    evaluated_at: datetime
    has_position: bool
    watchlist_enabled: bool
    material_change: bool = False
    hard_guard_due: bool = False
    explicit_user_request: bool = False
    review_after: datetime | None = None
    last_review_at: datetime | None = None
    last_full_research_at: datetime | None = None
    next_routine_review_at: datetime | None = None


@dataclass(frozen=True)
class ReviewPlan:
    policy_version: str
    symbol: str
    evaluated_at: datetime
    mode: ReviewMode
    analysis_depth: AnalysisDepth
    reason_codes: tuple[str, ...]
    last_review_at: datetime | None
    next_review_at: datetime | None
    routine_full_research_available: bool
    budget_override: bool


def plan_review(inputs: ReviewPolicyInput) -> ReviewPlan:
    """Return a deterministic permission plan without performing any analysis."""
    _require_aware(inputs.evaluated_at, "evaluated_at")
    for name, value in (
        ("review_after", inputs.review_after),
        ("last_review_at", inputs.last_review_at),
        ("last_full_research_at", inputs.last_full_research_at),
        ("next_routine_review_at", inputs.next_routine_review_at),
    ):
        if value is not None:
            _require_aware(value, name)

    routine_budget = not (
        inputs.last_full_research_at is not None
        and inputs.last_full_research_at.astimezone(inputs.evaluated_at.tzinfo).date()
        == inputs.evaluated_at.date()
    )

    if inputs.explicit_user_request:
        return _plan(inputs, ReviewMode.FULL_RESEARCH, AnalysisDepth.FULL,
                     ("explicit_user_request", "full_research_budget_override"), routine_budget, True)
    if inputs.material_change:
        return _plan(inputs, ReviewMode.FULL_RESEARCH, AnalysisDepth.FULL,
                     ("material_change", "full_research_budget_override"), routine_budget, True)
    if inputs.hard_guard_due:
        return _plan(inputs, ReviewMode.GUARD_ONLY, AnalysisDepth.GUARDS,
                     ("hard_guard_obligation",), routine_budget, False)
    if inputs.has_position:
        if inputs.review_after is not None and inputs.review_after <= inputs.evaluated_at:
            return _plan(inputs, ReviewMode.POSITION_REVIEW, AnalysisDepth.POSITION,
                         ("position_review_due",), routine_budget, False)
        return _plan(inputs, ReviewMode.GUARD_ONLY, AnalysisDepth.GUARDS,
                     ("position_guard_monitoring", "no_material_change"), routine_budget, False)
    if inputs.watchlist_enabled and routine_budget:
        return _plan(inputs, ReviewMode.FULL_RESEARCH, AnalysisDepth.FULL,
                     ("watchlist_routine_review", "routine_budget_available"), True, False)
    if inputs.watchlist_enabled:
        return _plan(inputs, ReviewMode.NO_REVIEW, AnalysisDepth.NONE,
                     ("routine_full_research_budget_exhausted",), False, False)
    return _plan(inputs, ReviewMode.NO_REVIEW, AnalysisDepth.NONE,
                 ("outside_active_personal_universe",), routine_budget, False)


def _plan(inputs, mode, depth, reasons, budget, override) -> ReviewPlan:
    return ReviewPlan(
        policy_version=REVIEW_POLICY_VERSION,
        symbol=inputs.symbol.strip().upper(),
        evaluated_at=inputs.evaluated_at,
        mode=mode,
        analysis_depth=depth,
        reason_codes=reasons,
        last_review_at=inputs.last_review_at,
        next_review_at=inputs.next_routine_review_at,
        routine_full_research_available=budget,
        budget_override=override,
    )


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
