"""Wire schemas for the Personal Universe API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


WatchlistPriorityValue = Literal["NORMAL", "FOCUS", "CORE"]
MembershipValue = Literal["POSITION", "WATCHLIST", "POSITION_AND_WATCHLIST"]
QuoteDisplayStateValue = Literal["live", "refreshing", "session_close", "stale", "unavailable"]


class WatchlistUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    enabled: bool | None = None
    priority: WatchlistPriorityValue | None = None
    note: str | None = Field(default=None, max_length=500)


class WatchlistItemResponse(BaseModel):
    symbol: str
    name: str
    enabled: bool
    priority: WatchlistPriorityValue
    note: str
    created_at: datetime
    updated_at: datetime


class PersonalUniverseItemResponse(BaseModel):
    symbol: str
    name: str
    membership: MembershipValue
    market: str | None = None
    watchlist_priority: WatchlistPriorityValue | None = None
    watchlist_note: str | None = None
    watchlist_enabled: bool | None = None
    position_quantity: float | None = None
    position_market_value: float | None = None
    sellable_quantity: float | None = None
    locked_quantity: float | None = None
    last_price: float | None = None
    change_percent: float | None = None
    quote_display_state: QuoteDisplayStateValue = "unavailable"
    quote_as_of: str | None = None
    formal_action: str | None = None
    decision_id: str | None = None
    decision_updated_at: str | None = None
    review_mode: str | None = None
    next_review_at: str | None = None


class PersonalUniverseCounts(BaseModel):
    positions: int
    watchlist: int
    combined: int


class PersonalUniverseResponse(BaseModel):
    generated_at: datetime
    items: list[PersonalUniverseItemResponse]
    counts: PersonalUniverseCounts
    data_state: Literal["ready", "partial", "degraded"]
    warnings: list[str] = Field(default_factory=list)
