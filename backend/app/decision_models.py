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
    enabled: bool
    version: int
    structured_conditions: tuple[dict[str, object], ...] = ()


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
