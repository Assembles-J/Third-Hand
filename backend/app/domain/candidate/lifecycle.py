"""Candidate lifecycle rules for research scheduling.

A research candidate is not a trade authorization.  Lifecycle transitions only
control when Third-Hand should spend research effort on a symbol; formal OPEN /
ADD / REDUCE still belongs to ActionPolicy.
"""
from __future__ import annotations

from dataclasses import dataclass


NEW = "NEW"
ANALYZING = "ANALYZING"
ACTIVE = "ACTIVE"
WAITING_TRIGGER = "WAITING_TRIGGER"
REACTIVATED = "REACTIVATED"
OPEN_READY_RESEARCH = "OPEN_READY_RESEARCH"
ARCHIVED = "ARCHIVED"

STATUSES = {
    NEW,
    ANALYZING,
    ACTIVE,
    WAITING_TRIGGER,
    REACTIVATED,
    OPEN_READY_RESEARCH,
    ARCHIVED,
}

RESEARCH_PRIORITIES = {"L0", "L1", "L2", "L3", "L4"}
SOURCE_TYPES = {
    "PAPER_POSITION",
    "DETERMINISTIC_ROTATION",
    "USER_ADDED",
    "OPPORTUNITY_SCAN",
}

# Deliberately explicit so a bug cannot silently revive/close a candidate.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    NEW: {ANALYZING, ACTIVE, WAITING_TRIGGER, ARCHIVED},
    ANALYZING: {ACTIVE, WAITING_TRIGGER, OPEN_READY_RESEARCH, ARCHIVED},
    ACTIVE: {ANALYZING, WAITING_TRIGGER, OPEN_READY_RESEARCH, ARCHIVED},
    WAITING_TRIGGER: {REACTIVATED, ARCHIVED},
    REACTIVATED: {ANALYZING, ACTIVE, WAITING_TRIGGER, OPEN_READY_RESEARCH, ARCHIVED},
    OPEN_READY_RESEARCH: {ACTIVE, ANALYZING, WAITING_TRIGGER, ARCHIVED},
    ARCHIVED: {NEW},
}


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    from_status: str
    to_status: str
    reason: str


def validate_status(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in STATUSES:
        raise ValueError(f"unsupported candidate lifecycle status: {value}")
    return normalized


def validate_priority(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in RESEARCH_PRIORITIES:
        raise ValueError(f"unsupported research priority: {value}")
    return normalized


def validate_source_type(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in SOURCE_TYPES:
        raise ValueError(f"unsupported candidate source type: {value}")
    return normalized


def transition_decision(current: str, target: str) -> TransitionDecision:
    current = validate_status(current)
    target = validate_status(target)
    if current == target:
        return TransitionDecision(True, current, target, "no_change")
    allowed = target in _ALLOWED_TRANSITIONS[current]
    return TransitionDecision(
        allowed,
        current,
        target,
        "allowed" if allowed else f"transition_not_allowed:{current}->{target}",
    )
