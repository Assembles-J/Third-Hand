"""Typed Personal Universe contracts.

These models describe user-owned attention state. They deliberately do not
carry BUY/ADD/REDUCE/EXIT authority and must not be projected into
DecisionContext as policy inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class WatchlistPriority(StrEnum):
    NORMAL = "NORMAL"
    FOCUS = "FOCUS"
    CORE = "CORE"


class PersonalUniverseMembership(StrEnum):
    POSITION = "POSITION"
    WATCHLIST = "WATCHLIST"
    POSITION_AND_WATCHLIST = "POSITION_AND_WATCHLIST"


@dataclass(frozen=True)
class WatchlistEntry:
    symbol: str
    name: str
    enabled: bool
    priority: WatchlistPriority
    note: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: dict[str, object]) -> "WatchlistEntry":
        def parse_timestamp(value: object) -> datetime:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("watchlist timestamp must be timezone-aware")
            return parsed

        raw_enabled = record.get("enabled", True)
        enabled = raw_enabled if isinstance(raw_enabled, bool) else bool(int(raw_enabled))
        priority_value = str(record.get("priority") or WatchlistPriority.NORMAL.value).upper()
        return cls(
            symbol=str(record["symbol"]).strip().upper(),
            name=str(record["name"]).strip(),
            enabled=enabled,
            priority=WatchlistPriority(priority_value),
            note=str(record.get("note") or ""),
            created_at=parse_timestamp(record["created_at"]),
            updated_at=parse_timestamp(record["updated_at"]),
        )


@dataclass(frozen=True)
class PersonalUniverseItem:
    symbol: str
    name: str
    membership: PersonalUniverseMembership
    market: str | None = None
    watchlist_priority: WatchlistPriority | None = None
    watchlist_note: str | None = None
    watchlist_enabled: bool | None = None
    position_quantity: float | None = None
    position_market_value: float | None = None
    sellable_quantity: float | None = None
    locked_quantity: float | None = None
    last_price: float | None = None
    change_percent: float | None = None
    quote_display_state: str = "unavailable"
    quote_as_of: str | None = None
    formal_action: str | None = None
    decision_id: str | None = None
    decision_updated_at: str | None = None
    review_mode: str | None = None
    next_review_at: str | None = None
