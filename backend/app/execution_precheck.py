"""Guard paper execution so a decision never fills on its own input quote."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


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

    gates = ((report.get("data_quality") or {}).get("action_gates") or [])
    action = str(report.get("action") or "").upper()
    gate = next((item for item in gates if str(item.get("action") or "").upper() == action), None)
    if action in {"OPEN", "ADD"} and (not gate or gate.get("permission") != "allowed"):
        return ExecutionCheck(False, "execution_action_gate_blocked")
    return ExecutionCheck(True)
