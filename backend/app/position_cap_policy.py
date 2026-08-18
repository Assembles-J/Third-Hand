"""Single deterministic authority for formal position concentration limits."""
from __future__ import annotations

from app import decision_config as config


def effective_position_cap_percent(context) -> float:
    """Return the formal cap shared by evidence and sizing.

    The system hard cap is always authoritative. An enabled PersonalRule may
    tighten it. TradePlan.max_position_percent intentionally remains audit/plan
    metadata in this policy version and is not promoted to sizing authority.
    """
    cap = float(config.SYSTEM_HARD_POSITION_CAP_PERCENT)
    rule = getattr(context, "personal_rule", None)
    if rule is not None and bool(getattr(rule, "enabled", True)):
        try:
            personal_cap = float(getattr(rule, "max_position_percent"))
        except (TypeError, ValueError):
            personal_cap = cap
        if personal_cap > 0:
            cap = min(cap, personal_cap)
    return cap


__all__ = ["effective_position_cap_percent"]
