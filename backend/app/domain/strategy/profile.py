"""Immutable strategy identity and authority metadata.

A StrategyProfile describes which existing policies produced a decision. It is
not a second action engine and has no execution authority of its own.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrategyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    strategy_version: str
    name: str
    holding_horizon: str
    strategic_timeframes: tuple[str, ...] = ()
    setup_timeframes: tuple[str, ...] = ()
    timing_timeframes: tuple[str, ...] = ()
    risk_timeframes: tuple[str, ...] = ()
    authority_matrix: dict[str, str]
    policy_versions: dict[str, str]


__all__ = ["StrategyProfile"]
