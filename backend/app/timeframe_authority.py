"""Explicit technical-timeframe authority without inventing absent data."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app import decision_config as config


class TimeframeAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategic_timeframes: tuple[str, ...] = ("weekly", "daily")
    position_management_timeframes: tuple[str, ...] = ("60m",)
    execution_timing_timeframes: tuple[str, ...] = ("15m", "5m")
    hard_risk_timeframes: tuple[str, ...] = ("realtime",)
    formal_technical_timeframe: str | None = None
    unavailable_timeframes: tuple[str, ...] = ()
    policy_version: str = config.TIMEFRAME_AUTHORITY_POLICY_VERSION


class TimeframeAuthorityPolicy:
    """Describe which declared timeframes actually have deterministic inputs."""

    version = config.TIMEFRAME_AUTHORITY_POLICY_VERSION

    def assess(self, context) -> TimeframeAuthority:
        # The current canonical context carries completed daily bars and one
        # daily-derived TechnicalSnapshot.  Realtime remains a risk/execution
        # trigger only; no intraday technical conclusion is manufactured.
        formal = "daily" if context.technical is not None else None
        unavailable = ["weekly", "60m", "15m", "5m"]
        if formal is None:
            unavailable.append("daily")
        return TimeframeAuthority(
            formal_technical_timeframe=formal,
            unavailable_timeframes=tuple(unavailable),
        )


__all__ = ["TimeframeAuthority", "TimeframeAuthorityPolicy"]
