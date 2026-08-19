"""Central, versioned thresholds for deterministic decision evidence."""
import hashlib
import json
import os

# v4 makes the effective position-cap authority explicit and shared with sizing.
EVIDENCE_VERSION = "evidence-v4-effective-position-cap"
# Atomic v3 remains the current schema/currentness contract. Intraday is an
# additive research source with its own separately persisted policy/authority
# versions below, so the Atomic schema identifier itself does not change.
ATOMIC_EVIDENCE_VERSION = "atomic-evidence-shadow-v3-financial-currentness"
# Phase 3 makes evidence aggregation reproducible and auditable. Phase 4 may
# use only its deterministic adverse new-risk veto; research never upgrades an
# action or manufactures an exit/reduce recommendation.
DIMENSION_AGGREGATION_POLICY_VERSION = "dimension-aggregation-v1-fact-polarity"
FACT_POLARITY_POLICY_VERSION = "fact-polarity-v1-atomic-record-authority"
FINANCIAL_CURRENTNESS_POLICY_VERSION = "financial-currentness-v1-event-aware-report-period"
FUNDAMENTAL_AGGREGATION_POLICY_VERSION = "fundamental-aggregation-v2-historical-currentness"
RESEARCH_AGGREGATION_POLICY_VERSION = "research-aggregation-v1-domain-consensus"
SEMANTIC_INVARIANT_VALIDATOR_VERSION = "research-semantic-invariants-v2-financial-currentness"
DECISION_ARBITER_POLICY_VERSION = "decision-arbiter-v4-adverse-research-new-risk-veto"
RESEARCH_DECISION_POLICY_VERSION = "research-decision-v1-adverse-new-risk-veto"
RESEARCH_ADVERSE_MIN_EVIDENCE_CONFIDENCE = 0.60
TIMEFRAME_AUTHORITY_POLICY_VERSION = "timeframe-authority-v2-weekly-context"
INTRADAY_TIMEFRAME_POLICY_VERSION = "intraday-timeframe-evidence-v1-completed-bars"
INTRADAY_RESEARCH_AUTHORITY_VERSION = "intraday-research-authority-v1-no-formal-effect"
DECISION_CONTINUITY_POLICY_VERSION = "decision-continuity-v3-material-fingerprint"
MODEL_POLICY_VERSION = "model-policy-v3-compound-structured-recovery"
FEEDBACK_POLICY_VERSION = "feedback-v1-audit-only-no-auto-tune"
# Formal Decision correctness must not depend on a scheduler having warmed the
# same caches first. This policy turns missing/stale mandatory requirements into
# one bounded acquisition attempt before immutable Decision inputs are frozen.
MANDATORY_ACQUISITION_POLICY_VERSION = "mandatory-acquisition-v1-pre-decision"
MANDATORY_ACQUISITION_BUDGET_POLICY_VERSION = "mandatory-acquisition-budget-v1-bounded"
# v5 invalidates historical reports that could have been sized against a looser
# hard-coded 20% cap than the evidence/personal-rule authority.
ACTION_POLICY_VERSION = "swing-policy-v5-effective-position-cap"
OPEN_GATE_AUDIT_VERSION = "open-gate-audit-v1"
# v2 records the Day-0 shift from wall-clock TTL checks for daily data to
# latest-completed-exchange-session semantics. Thresholds are unchanged; the
# version bump makes the already-deployed behavior auditable in DecisionReport.
FRESHNESS_POLICY_VERSION = "freshness-v2-session-aware"
# v1 adds a separate, deterministic cross-source authority layer. Individually
# fresh records can still conflict when their observed market dates disagree.
CANONICAL_INPUT_POLICY_VERSION = "canonical-input-v1-cross-source-consistency"
# Instrument metadata is the formal market authority when present. Symbol-shape
# inference remains a compatibility fallback only.
MARKET_IDENTITY_POLICY_VERSION = "market-identity-v2-instrument-authority"
# Market-regime evidence may only apply to the same explicit market. Missing HK/
# US providers degrade to unknown instead of inheriting A-share benchmarks.
MARKET_REGIME_POLICY_VERSION = "market-regime-v2-market-scoped"
# v2 keeps known earnings obligations durable across the scheduled date and
# records source rank/conflicts without granting events directional authority.
CORPORATE_EVENT_POLICY_VERSION = "corporate-event-v2-persistent-lifecycle"
PRE_EVENT_BLOCK_SESSIONS = 1
# v7 makes execution consume only an explicit order quantity. A numeric zero can
# never fall back to the resulting/target position quantity.
EXECUTION_POLICY_VERSION = "execution-v7-explicit-order-quantity"
CANDIDATE_SELECTION_VERSION = "candidate-rotation-v1"
OPPORTUNITY_SCORING_VERSION = "research-priority-v1"
# Decision-input freshness stays conservative. Execution is a separate boundary:
# it may consume a strictly later observed intraday quote under EXECUTION_POLICY_VERSION.
QUOTE_MAX_AGE_SECONDS = 86_400
EXECUTION_QUOTE_MAX_AGE_SECONDS = 900
MARKET_INTELLIGENCE_MAX_AGE_SECONDS = 86_400
DAILY_BAR_MAX_AGE_DAYS = 2
RISK_MAX_AGE_DAYS = 2
DECISION_SHADOW_MODE = os.getenv("DECISION_SHADOW_MODE", "true").lower() not in {"0", "false", "no"}
DECISION_SIZING_ENABLED = os.getenv("DECISION_SIZING_ENABLED", "false").lower() in {"1", "true", "yes"}
DECISION_AI_ENABLED = os.getenv("DECISION_AI_ENABLED", "false").lower() in {"1", "true", "yes"}
SIZING_VERSION = "risk-sizing-v3-effective-position-cap"
DECISION_RESEARCH_PROMPT_VERSION = "decision-research-v1"
MAX_LIQUIDITY_VOLUME_FRACTION = 0.10
SYSTEM_HARD_POSITION_CAP_PERCENT = 20.0
NEAR_POSITION_CAP_RATIO = 0.90
POSITION_CAP_EXCESS_MILD_PERCENT = 10.0


def audit_version_snapshot() -> dict[str, str]:
    """Non-secret immutable identity recorded with each Day-0 observation report."""
    values = {
        "git_commit": os.getenv("GIT_COMMIT", "unknown"),
        "context_schema_version": "context-v4-single-cny",
        "evidence_version": EVIDENCE_VERSION,
        "atomic_evidence_version": ATOMIC_EVIDENCE_VERSION,
        "dimension_aggregation_policy_version": DIMENSION_AGGREGATION_POLICY_VERSION,
        "fact_polarity_policy_version": FACT_POLARITY_POLICY_VERSION,
        "financial_currentness_policy_version": FINANCIAL_CURRENTNESS_POLICY_VERSION,
        "fundamental_aggregation_policy_version": FUNDAMENTAL_AGGREGATION_POLICY_VERSION,
        "research_aggregation_policy_version": RESEARCH_AGGREGATION_POLICY_VERSION,
        "semantic_invariant_validator_version": SEMANTIC_INVARIANT_VALIDATOR_VERSION,
        "decision_arbiter_policy_version": DECISION_ARBITER_POLICY_VERSION,
        "research_decision_policy_version": RESEARCH_DECISION_POLICY_VERSION,
        "timeframe_authority_policy_version": TIMEFRAME_AUTHORITY_POLICY_VERSION,
        "intraday_timeframe_policy_version": INTRADAY_TIMEFRAME_POLICY_VERSION,
        "intraday_research_authority_version": INTRADAY_RESEARCH_AUTHORITY_VERSION,
        "decision_continuity_policy_version": DECISION_CONTINUITY_POLICY_VERSION,
        "model_policy_version": MODEL_POLICY_VERSION,
        "feedback_policy_version": FEEDBACK_POLICY_VERSION,
        "mandatory_acquisition_policy_version": MANDATORY_ACQUISITION_POLICY_VERSION,
        "mandatory_acquisition_budget_policy_version": MANDATORY_ACQUISITION_BUDGET_POLICY_VERSION,
        "action_policy_version": ACTION_POLICY_VERSION,
        "open_gate_audit_version": OPEN_GATE_AUDIT_VERSION,
        "sizing_version": SIZING_VERSION,
        "freshness_policy_version": FRESHNESS_POLICY_VERSION,
        "canonical_input_policy_version": CANONICAL_INPUT_POLICY_VERSION,
        "market_identity_policy_version": MARKET_IDENTITY_POLICY_VERSION,
        "market_regime_policy_version": MARKET_REGIME_POLICY_VERSION,
        "corporate_event_policy_version": CORPORATE_EVENT_POLICY_VERSION,
        "execution_policy_version": EXECUTION_POLICY_VERSION,
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