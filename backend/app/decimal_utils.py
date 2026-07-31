"""Decimal helpers for prices and amounts persisted by the research system."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any) -> Decimal | None:
    """Convert a provider value without introducing binary floating point noise."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "null"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def decimal_text(value: Any) -> str | None:
    """Return the canonical, JSON-safe representation used in SQLite."""
    number = to_decimal(value)
    if number is None:
        return None
    return format(number, "f")
