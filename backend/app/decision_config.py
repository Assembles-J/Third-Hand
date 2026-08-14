"""Central, versioned thresholds for deterministic decision evidence."""
import hashlib
import json
import os

EVIDENCE_VERSION = "evidence-v2-usage-scope"
# v3 is a Day-0 correctness break: REDUCE now requires an existing position.
# Bumping the version prevents historical v2 empty-position REDUCE reports from
# remaining eligible for next-session execution after deployment.
ACTION_POLICY_VERSION = "swing-policy-v3-position-action-semantics"
OPEN_GATE_AUDIT_VERSION = "open-gate-audit-v1"
FRESHNESS_POLICY_VERSION = "freshness-v1"
CANDIDATE_SELECTION_VERSION = "candidate-rotation-v1"
OPPORTUNITY_SCORING_VERSION = "research-priority-v1"
# P0 deliberately applies one conservative, documented age budget across the
# daily decision flow. Intraday execution is not supported by this policy.
QUOTE_MAX_AGE_SECONDS = 86_400
MARKET_INTELLIGENCE_MAX_AGE_SECONDS = 86_400
DAILY_BAR_MAX_AGE_DAYS = 2
RISK_MAX_AGE_DAYS = 2
DECISION_SHADOW_MODE = os.getenv("DECISION_SHADOW_MODE", "true").lower() not in {"0", "false", "no"}
DECISION_SIZING_ENABLED = os.getenv("DECISION_SIZING_ENABLED", "false").lower() in {"1", "true", "yes"}
DECISION_AI_ENABLED = os.getenv("DECISION_AI_ENABLED", "false").lower() in {"1", "true", "yes"}
SIZING_VERSION = "risk-sizing-v1"
DECISION_RESEARCH_PROMPT_VERSION = "decision-research-v1"
MAX_LIQUIDITY_VOLUME_FRACTION = 0.10
NEAR_POSITION_CAP_RATIO = 0.90
POSITION_CAP_EXCESS_MILD_PERCENT = 10.0


def audit_version_snapshot() -> dict[str, str]:
    """Non-secret immutable identity recorded with each Day-0 observation report."""
    values = {
        "git_commit": os.getenv("GIT_COMMIT", "unknown"),
        "context_schema_version": "context-v1",
        "evidence_version": EVIDENCE_VERSION,
        "action_policy_version": ACTION_POLICY_VERSION,
        "open_gate_audit_version": OPEN_GATE_AUDIT_VERSION,
        "sizing_version": SIZING_VERSION,
        "freshness_policy_version": FRESHNESS_POLICY_VERSION,
        "decision_prompt_version": DECISION_RESEARCH_PROMPT_VERSION,
        "candidate_selection_version": CANDIDATE_SELECTION_VERSION,
        "opportunity_scoring_version": OPPORTUNITY_SCORING_VERSION,
    }
    values["config_hash"] = hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()
    return values


POSITION_CAP_EXCESS_MEDIUM_PERCENT = 30.0
LARGE_PROFIT_PERCENT = 20.0
CASH_CONSTRAINED_PERCENT = 5.0
RSI_HOT = 70.0
RSI_COLD = 30.0
HIGH_ATR_PERCENT = 4.0
HIGH_DRAWDOWN_PERCENT = -15.0
HIGH_DOWNSIDE_PROBABILITY_PERCENT = 20.0
HIGH_ANNUALIZED_VOLATILITY_PERCENT = 50.0
