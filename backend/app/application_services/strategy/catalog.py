"""Versioned strategy catalog.

Profiles bind names and authority metadata to the deterministic policies already
used by the formal decision pipeline. They deliberately do not evaluate actions.
"""
from __future__ import annotations

from app.domain.strategy import StrategyProfile


SWING_V1_ID = "SWING_V1"
SWING_V1_VERSION = "1.0.0"


def swing_v1_profile(*, action_policy_version: str, timeframe_policy_version: str) -> StrategyProfile:
    return StrategyProfile(
        strategy_id=SWING_V1_ID,
        strategy_version=SWING_V1_VERSION,
        name="Swing",
        holding_horizon="3-20 trading sessions",
        strategic_timeframes=("weekly", "daily"),
        setup_timeframes=("60m",),
        timing_timeframes=("15m", "5m"),
        risk_timeframes=("realtime",),
        authority_matrix={
            "weekly": "strategic_structure",
            "daily": "strategic_structure",
            "60m": "setup_position_management",
            "15m": "execution_timing",
            "5m": "execution_timing",
            "realtime": "hard_risk_execution",
            "fundamental": "quality_risk_context",
            "financial": "quality_currentness",
            "corporate_event": "deterministic_risk_gate",
            "market_regime": "strategic_context",
            "news": "research_context",
            "order_flow": "timing_evidence_only",
            "ai": "research_explanation_only",
        },
        policy_versions={
            "action_policy": action_policy_version,
            "timeframe_authority": timeframe_policy_version,
        },
    )


__all__ = ["SWING_V1_ID", "SWING_V1_VERSION", "swing_v1_profile"]
