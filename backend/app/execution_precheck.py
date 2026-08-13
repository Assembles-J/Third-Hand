"""Guard paper execution so a daily decision cannot fill on its own input bar."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class ExecutionCheck:
    allowed: bool
    reason: str | None = None


def _date(value: object) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def validate_daily_execution(report: dict[str, object], quote: dict[str, object] | None) -> ExecutionCheck:
    """Allow a report only when a later market date supplies the fill price."""
    if not quote or quote.get("price") is None:
        return ExecutionCheck(False, "execution_quote_missing")
    decision_date = _date(report.get("market_as_of") or report.get("generated_at"))
    fill_date = _date(quote.get("as_of") or quote.get("retrieved_at"))
    if not decision_date or not fill_date:
        return ExecutionCheck(False, "execution_time_unknown")
    if fill_date <= decision_date:
        return ExecutionCheck(False, "execution_not_due_next_market_session")
    gates = ((report.get("data_quality") or {}).get("action_gates") or [])
    action = str(report.get("action") or "").upper()
    gate = next((item for item in gates if str(item.get("action") or "").upper() == action), None)
    if action in {"OPEN", "ADD"} and (not gate or gate.get("permission") != "allowed"):
        return ExecutionCheck(False, "execution_action_gate_blocked")
    return ExecutionCheck(True)
