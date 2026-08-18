"""Central, versioned thresholds for deterministic decision evidence."""
import hashlib
import json
import os

# v3 changes POLICY evidence authority: technical price/location uses the
# canonical quote/daily view and stale/conflicted risk evidence is research-only.
EVIDENCE_VERSION = "evidence-v3-canonical-market-inputs"
# Phase 2 runs this compact fact representation beside current evidence. v2 adds
# point-in-time persisted Company Intelligence facts without formal authority.
ATOMIC_EVIDENCE_VERSION = "atomic-evidence-shadow-v2-company-research"
# Phase 3 makes evidence aggregation reproducible and auditable. Phase 4 may
# use only its deterministic adverse new-risk veto; research never upgrades an
# action or manufactures an exit/reduce recommendation.
DIMENSION_AGGREGATION_POLICY_VERSION = "dimension-aggregation-v1-fact-polarity"
FACT_POLARITY_POLICY_VERSION = "fact-polarity-v1-atomic-record-authority"
FUNDAMENTAL_AGGREGATION_POLICY_VERSION = "fundamental-aggregation-v1-dimension-consensus"
RESEARCH_AGGREGATION_POLICY_VERSION = "research-aggregation-v1-domain-consensus"
SEMANTIC_INVARIANT_VALIDATOR_VERSION = "research-semantic-invariants-v1"
DECISION_ARBITER_POLICY_VERSION = "decision-arbiter-v4-adverse-research-new-risk-veto"
RESEARCH_DECISION_POLICY_VERSION = "research-decision-v1-adverse-new-risk-veto"
RESEARCH_ADVERSE_MIN_EVIDENCE_CONFIDENCE = 0.60
TIMEFRAME_AUTHORITY_POLICY_VERSION = "timeframe-authority-v2-weekly-context"
DECISION_CONTINUITY_POLICY_VERSION = "decision-continuity-v3-material-fingerprint"
MODEL_POLICY_VERSION = "model-policy-v3-compound-structured-recovery"
FEEDBACK_POLICY_VERSION = "feedback-v1-audit-only-no-auto-tune"
# v3 is a Day-0 correctness break: REDUCE now requires an existing position.
# Bumping the version prevents historical v2 empty-position REDUCE reports from
# remaining eligible for next-session execution after deployment.
ACTION_POLICY_VERSION = "swing-policy-v4-post-entry-coherence"
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
# Scheduled earnings are deterministic neutral-material facts. The policy only
# blocks new risk immediately before disclosure; it never infers event direction.
CORPORATE_EVENT_POLICY_VERSION = "corporate-event-v1-pre-earnings-gate"
PRE_EVENT_BLOCK_SESSIONS = 1
# v2 fixes A-share execution semantics: OPEN/ADD may fill on a strictly later
# observed quote in the same trading day, while T+1 remains a SELL-availability
# constraint enforced by the paper ledger.
EXECUTION_POLICY_VERSION = "execution-v6-session-freshness-gate"
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
SIZING_VERSION = "risk-sizing-v2-market-execution-precheck"
DECISION_RESEARCH_PROMPT_VERSION = "decision-research-v1"
MAX_LIQUIDITY_VOLUME_FRACTION = 0.10
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
        "fundamental_aggregation_policy_version": FUNDAMENTAL_AGGREGATION_POLICY_VERSION,
        "research_aggregation_policy_version": RESEARCH_AGGREGATION_POLICY_VERSION,
        "semantic_invariant_validator_version": SEMANTIC_INVARIANT_VALIDATOR_VERSION,
        "decision_arbiter_policy_version": DECISION_ARBITER_POLICY_VERSION,
        "research_decision_policy_version": RESEARCH_DECISION_POLICY_VERSION,
        "timeframe_authority_policy_version": TIMEFRAME_AUTHORITY_POLICY_VERSION,
        "decision_continuity_policy_version": DECISION_CONTINUITY_POLICY_VERSION,
        "model_policy_version": MODEL_POLICY_VERSION,
        "feedback_policy_version": FEEDBACK_POLICY_VERSION,
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
