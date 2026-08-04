"""Strict, immutable schemas for the phase-1 decision context."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DecisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AccountSnapshot(DecisionModel):
    available_cash: float
    total_market_value: float | None
    total_assets: float | None
    cash_percent: float | None
    account_currency: str = "CNY"


class PositionSnapshot(DecisionModel):
    quantity: float
    average_cost: float
    opened_at: str | None = None
    current_price: float | None
    market_value: float | None
    cost_value: float
    unrealized_pnl: float | None
    unrealized_pnl_percent: float | None
    position_percent: float | None


class QuoteSnapshot(DecisionModel):
    price: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    change_percent: float | None = None
    volume: float | None = None
    amount: float | None = None
    source: str
    as_of: str | None = None
    retrieved_at: str | None = None
    is_realtime: bool | None = None
    delay_seconds: float | None = None
    freshness_status: str | None = None


class DailyBarSummary(DecisionModel):
    count: int = Field(ge=0)
    first_trading_date: str | None = None
    last_trading_date: str | None = None
    last_close: float | None = None
    source: str | None = None


class TechnicalSnapshot(DecisionModel):
    as_of: str
    sample_count: int
    trend: str
    trend_label: str
    sma20: float | None = None
    sma60: float | None = None
    rsi14: float
    rsi_state: str
    macd_histogram: float
    atr_percent: float
    drawdown_60d_percent: float


class RiskSnapshot(DecisionModel):
    as_of: str | None = None
    sample_count: int | None = None
    historical_downside_probability: float | None = None
    annualized_volatility_percent: float | None = None
    risk_level: str | None = None
    source: str = "risk_cache"


class MarketRegimeSnapshot(DecisionModel):
    status: str
    regime: str | None = None
    source: str | None = None
    as_of: str | None = None


class RelativeStrengthSnapshot(DecisionModel):
    status: str
    benchmark_symbol: str | None = None
    benchmark_name: str | None = None
    label: str | None = None
    source: str = "portfolio_analysis_cache"


class EventSnapshot(DecisionModel):
    event_id: str
    title: str
    impact: Literal["positive", "negative", "neutral", "uncertain"] = "uncertain"
    source: str
    source_reference: str | None = None
    published_at: str | None = None
    summary: str | None = None


class TradePlanSnapshot(DecisionModel):
    plan_id: str
    horizon: str
    thesis: str
    entry_condition: str
    add_condition: str
    reduce_condition: str
    exit_condition: str
    max_position_percent: float
    risk_budget_percent: float
    invalidation_price: float | None = None
    enabled: bool
    version: int
    structured_conditions: tuple[dict[str, object], ...] = ()
    is_draft: bool = False


class PersonalRuleSnapshot(DecisionModel):
    rule_id: str
    scope: str
    max_position_percent: float
    loss_review_percent: float
    volatility_review_percent: float
    enabled: bool
    version: int


class InstrumentSnapshot(DecisionModel):
    symbol: str
    market: str
    currency: str
    lot_size: int | None = None
    price_tick: str | None = None
    source: str
    as_of: str


class DataQualitySummary(DecisionModel):
    status: Literal["ready", "degraded", "blocked"]
    score_percent: int = Field(ge=0, le=100)
    missing_fields: tuple[str, ...] = ()
    stale_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class EvidenceItem(DecisionModel):
    evidence_id: str
    category: Literal["position", "price", "trend", "momentum", "volatility", "volume", "event", "fundamental", "market", "relative", "liquidity", "plan", "risk", "data_quality"]
    direction: Literal["positive", "negative", "neutral", "uncertain"]
    strength: float = Field(ge=0, le=1)
    title: str
    description: str
    value: float | str | bool | None = None
    threshold: float | str | None = None
    source: str
    as_of: datetime | str | None = None
    fresh: bool
    rule_id: str | None = None
    source_reference: str | None = None


class ActionCandidate(DecisionModel):
    action: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"]
    priority: int = Field(ge=0, le=100)
    policy_score: float = Field(ge=0, le=1)
    supporting_evidence_ids: tuple[str, ...] = ()
    opposing_evidence_ids: tuple[str, ...] = ()
    triggered_rule_ids: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()


class ReasoningStep(DecisionModel):
    stage: Literal["evidence", "conflict", "uncertainty"]
    summary: str = Field(min_length=1, max_length=400)
    evidence_ids: tuple[str, ...] = ()


class AiResearchAssessment(DecisionModel):
    thesis_status: Literal["strengthened", "unchanged", "weakened", "invalidated", "unknown"]
    preferred_action: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"]
    supporting_evidence_ids: tuple[str, ...] = ()
    opposing_evidence_ids: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    reasoning_steps: tuple[ReasoningStep, ...] = ()
    uncertainty: Literal["low", "medium", "high"]
    summary: str = Field(min_length=1, max_length=800)


class ShadowDecisionReport(DecisionModel):
    shadow_id: str
    context_id: str
    symbol: str
    generated_at: datetime
    status: Literal["READY", "BLOCKED", "DEGRADED"]
    evidence: tuple[EvidenceItem, ...]
    action_candidates: tuple[ActionCandidate, ...]
    sizing: "PositionSizingResult | None" = None
    ai_assessment: AiResearchAssessment | None = None
    guarded_preferred_action: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"] | None = None
    policy_version: str
    input_hash: str
    shadow_mode: Literal[True] = True


class PositionSizingResult(DecisionModel):
    status: Literal["ready", "blocked", "not_applicable"]
    current_quantity: float
    suggested_quantity: float | None = None
    target_quantity: float | None = None
    current_position_percent: float | None = None
    target_position_percent: float | None = None
    quantity_by_risk: float | None = None
    quantity_by_cash: float | None = None
    quantity_by_position_cap: float | None = None
    quantity_by_liquidity: float | None = None
    lot_size: int | None = None
    entry_price: float | None = None
    invalidation_price: float | None = None
    risk_per_share: float | None = None
    risk_capital: float | None = None
    blocked_reasons: tuple[str, ...] = ()
    sizing_version: str


class OperationItem(DecisionModel):
    """A compact, actionable workbench item derived from policy and the trade plan.

    It intentionally keeps the AI out of price/quantity invention: all numbers are
    sourced from the current quote, the enabled plan, or the sizing engine.
    """
    kind: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED", "COMPLETE"]
    title: str
    trigger: str
    reference_price: float | None = None
    invalidation_price: float | None = None
    suggested_quantity: float | None = None
    target_quantity: float | None = None
    status: Literal["ready", "needs_input"]
    blockers: tuple[str, ...] = ()


class DecisionReport(DecisionModel):
    decision_id: str
    context_id: str
    symbol: str
    generated_at: datetime
    status: Literal["READY", "BLOCKED", "DEGRADED"]
    action: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"]
    summary: str
    evidence: tuple[EvidenceItem, ...]
    action_candidates: tuple[ActionCandidate, ...]
    operation_items: tuple[OperationItem, ...] = ()
    ai_assessment: AiResearchAssessment | None = None
    ai_status: Literal["succeeded", "failed", "skipped", "disabled"] = "disabled"
    ai_error_code: str | None = None
    market_price: float | None = None
    market_change_percent: float | None = None
    market_as_of: str | None = None
    sizing: PositionSizingResult | None = None
    policy_version: str
    prompt_version: str | None = None
    schema_version: str = "context-v1"
    model: str | None = None
    input_hash: str
    automatic_execution: Literal[False] = False


class DecisionContext(DecisionModel):
    context_id: str
    symbol: str
    name: str
    generated_at: datetime
    decision_horizon: Literal["intraday", "swing", "position"]
    account: AccountSnapshot
    position: PositionSnapshot | None
    quote: QuoteSnapshot | None
    daily_bars: DailyBarSummary
    technical: TechnicalSnapshot | None
    risk: RiskSnapshot | None
    market_regime: MarketRegimeSnapshot | None
    relative_strength: RelativeStrengthSnapshot | None
    events: tuple[EventSnapshot, ...]
    trade_plan: TradePlanSnapshot | None
    personal_rule: PersonalRuleSnapshot | None
    instrument: InstrumentSnapshot | None
    data_quality: DataQualitySummary
    source_versions: dict[str, str]
    input_hash: str
