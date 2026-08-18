"""Guard paper execution so a decision never fills on its own input quote."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from app.decision_semantics import action_gate_for, formal_action_from_report


BEIJING_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class ExecutionCheck:
    allowed: bool
    reason: str | None = None


def _has_clock(value: object) -> bool:
    text = str(value or "").strip()
    return "T" in text or " " in text


def _datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BEIJING_TZ)
    return parsed.astimezone(BEIJING_TZ)


def _observed_at(primary: object, fallback: object) -> datetime | None:
    """Prefer an exchange/provider timestamp; avoid treating a date-only value as midnight."""
    if _has_clock(primary):
        parsed = _datetime(primary)
        if parsed is not None:
            return parsed
    return _datetime(fallback) or _datetime(primary)


def execution_quote_observed_at(quote: dict[str, object] | None) -> str | None:
    """Return the canonical timestamp used to prove a fill was observed after its decision."""
    if not quote:
        return None
    observed = _observed_at(quote.get("as_of"), quote.get("retrieved_at"))
    return observed.isoformat() if observed is not None else None


def validate_daily_execution(report: dict[str, object], quote: dict[str, object] | None) -> ExecutionCheck:
    """Allow execution only on a strictly later independently observed quote.

    A-share T+1 constrains SELL availability, not BUY timing.  The paper ledger
    enforces that same-day BUY quantities are not sellable.  This precheck only
    prevents same-cycle fills by requiring a quote observed after the decision
    input quote, including when both observations occur on the same trading day.
    """
    if not quote or quote.get("price") is None:
        return ExecutionCheck(False, "execution_quote_missing")

    decision_at = _observed_at(report.get("market_as_of"), report.get("generated_at"))
    fill_at = _observed_at(quote.get("as_of"), quote.get("retrieved_at"))
    if not decision_at or not fill_at:
        return ExecutionCheck(False, "execution_time_unknown")
    if fill_at <= decision_at:
        return ExecutionCheck(False, "execution_not_due_later_quote")

    # DecisionContinuity owns the cooldown value, but execution must enforce it
    # at the last deterministic boundary.  A persisted report without a valid
    # timestamp remains executable under the normal quote/gate checks; a bad
    # optional audit field must never be silently interpreted as a future time.
    memory = report.get("decision_memory")
    cooldown_until = _datetime(memory.get("cooldown_until")) if isinstance(memory, Mapping) else None
    if cooldown_until is not None and fill_at < cooldown_until:
        return ExecutionCheck(False, "execution_cooldown_active")

    gates = ((report.get("data_quality") or {}).get("action_gates") or [])
    formal_action = formal_action_from_report(report)
    gate_action = action_gate_for(formal_action)
    gate = next((item for item in gates if str(item.get("action") or "").upper() == gate_action), None)
    if gate_action and (not gate or gate.get("permission") != "allowed"):
        return ExecutionCheck(False, "execution_action_gate_blocked")
    return ExecutionCheck(True)
