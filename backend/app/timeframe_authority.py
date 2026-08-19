"""Versioned multi-timeframe authority with asymmetric action semantics."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app import decision_config as config


class TimeframeAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategic_timeframes: tuple[str, ...] = ("weekly", "daily")
    position_management_timeframes: tuple[str, ...] = ("60m",)
    execution_timing_timeframes: tuple[str, ...] = ("15m", "5m")
    hard_risk_timeframes: tuple[str, ...] = ("realtime",)
    formal_technical_timeframe: str | None = None
    available_timeframes: tuple[str, ...] = ()
    unavailable_timeframes: tuple[str, ...] = ()
    weekly_state: str = "UNKNOWN"
    daily_state: str = "UNKNOWN"
    state_60m: str = "UNKNOWN"
    state_15m: str = "UNKNOWN"
    state_5m: str = "UNKNOWN"
    confirmation_state: Literal["CONFIRMED", "UNCONFIRMED", "CONFLICT", "UNAVAILABLE", "NOT_APPLIED"] = "NOT_APPLIED"
    conflict_state: Literal["NONE", "LOWER_TIMEFRAME", "HIGHER_TIMEFRAME", "DATA_UNAVAILABLE"] = "NONE"
    reason_codes: tuple[str, ...] = ()
    policy_version: str = config.TIMEFRAME_AUTHORITY_POLICY_VERSION


class TimeframeAuthorityPolicy:
    """Conservative first version of formal multi-timeframe semantics.

    Higher timeframes define structure. Lower timeframes can only delay/downgrade
    *new risk*: BUY -> WAIT or ADD -> HOLD. Lower-timeframe strength can never
    upgrade WAIT/BLOCKED/HOLD into BUY/ADD, and lower-timeframe weakness alone
    can never create REDUCE/EXIT for an existing position.
    """

    version = config.TIMEFRAME_AUTHORITY_POLICY_VERSION

    def assess(self, context, atomic_evidence=None) -> TimeframeAuthority:
        weekly = self._weekly_state(context)
        daily = self._daily_state(context)
        intraday = self._intraday_states(atomic_evidence)
        available = ["daily"] if context.technical is not None else []
        if weekly != "UNKNOWN":
            available.insert(0, "weekly")
        for timeframe in ("60m", "15m", "5m"):
            if intraday[timeframe]["availability"] == "AVAILABLE":
                available.append(timeframe)
        unavailable = [
            timeframe
            for timeframe in ("weekly", "daily", "60m", "15m", "5m")
            if timeframe not in available
        ]
        return TimeframeAuthority(
            formal_technical_timeframe="daily" if context.technical is not None else None,
            available_timeframes=tuple(available),
            unavailable_timeframes=tuple(unavailable),
            weekly_state=weekly,
            daily_state=daily,
            state_60m=intraday["60m"]["state"],
            state_15m=intraday["15m"]["state"],
            state_5m=intraday["5m"]["state"],
        )

    def apply(self, context, atomic_evidence, decision):
        authority = self.assess(context, atomic_evidence)
        proposed_action = decision.action
        if proposed_action not in {"BUY", "ADD"}:
            authority = authority.model_copy(update={
                "confirmation_state": "NOT_APPLIED",
                "conflict_state": "NONE",
                "reason_codes": (),
            })
            return decision, authority, self.material_state(authority)

        intraday = self._intraday_states(atomic_evidence)
        reasons: list[str] = []
        unavailable = [
            timeframe
            for timeframe in ("60m", "15m", "5m")
            if intraday[timeframe]["availability"] != "AVAILABLE"
        ]
        higher_conflict = authority.weekly_state == "DOWN" or authority.daily_state == "DOWN"
        lower_conflict = (
            authority.state_60m == "WEAK"
            or (authority.state_15m == "WEAK" and authority.state_5m == "WEAK")
        )
        lower_confirmed = (
            authority.state_60m == "SUPPORTIVE"
            and any(state == "SUPPORTIVE" for state in (authority.state_15m, authority.state_5m))
        )

        if higher_conflict:
            confirmation, conflict = "CONFLICT", "HIGHER_TIMEFRAME"
            reasons.append("timeframe.higher_structure_conflict")
        elif unavailable:
            confirmation, conflict = "UNAVAILABLE", "DATA_UNAVAILABLE"
            reasons.extend(
                f"timeframe.{timeframe}.{intraday[timeframe]['availability'].lower()}"
                for timeframe in unavailable
            )
        elif lower_conflict:
            confirmation, conflict = "CONFLICT", "LOWER_TIMEFRAME"
            if authority.state_60m == "WEAK":
                reasons.append("timeframe.60m.weak")
            if authority.state_15m == "WEAK" and authority.state_5m == "WEAK":
                reasons.append("timeframe.15m_5m.weak")
        elif lower_confirmed:
            confirmation, conflict = "CONFIRMED", "NONE"
            reasons.append("timeframe.new_risk_confirmed")
        else:
            confirmation, conflict = "UNCONFIRMED", "NONE"
            reasons.append("timeframe.new_risk_unconfirmed")

        authority = authority.model_copy(update={
            "confirmation_state": confirmation,
            "conflict_state": conflict,
            "reason_codes": tuple(reasons),
        })
        if confirmation == "CONFIRMED":
            return decision, authority, self.material_state(authority)

        downgraded_action = "WAIT" if proposed_action == "BUY" else "HOLD"
        downgraded = self._with_action(
            decision,
            downgraded_action,
            (*reasons, "timeframe.new_risk_downgraded"),
        )
        return downgraded, authority, self.material_state(authority)

    @staticmethod
    def material_state(authority: TimeframeAuthority) -> dict[str, object]:
        """Only stable policy states belong in DecisionContinuity fingerprint."""
        return {
            "policy_version": authority.policy_version,
            "weekly_state": authority.weekly_state,
            "daily_state": authority.daily_state,
            "60m_state": authority.state_60m,
            "15m_state": authority.state_15m,
            "5m_state": authority.state_5m,
            "confirmation_state": authority.confirmation_state,
            "conflict_state": authority.conflict_state,
        }

    @staticmethod
    def _weekly_state(context) -> str:
        for item in getattr(context, "timeframe_technicals", ()) or ():
            if getattr(item, "timeframe", None) == "weekly":
                return str(getattr(item, "trend", "unknown") or "unknown").upper()
        return "UNKNOWN"

    @staticmethod
    def _daily_state(context) -> str:
        technical = getattr(context, "technical", None)
        if technical is None:
            return "UNKNOWN"
        return str(getattr(technical, "trend", "unknown") or "unknown").upper()

    @staticmethod
    def _intraday_states(snapshot) -> dict[str, dict[str, str]]:
        result = {
            timeframe: {"availability": "MISSING", "state": "UNKNOWN"}
            for timeframe in ("60m", "15m", "5m")
        }
        if snapshot is None:
            return result
        availability = {
            item.capability: str(item.status).upper()
            for item in getattr(snapshot, "availability", ())
        }
        facts = {
            item.metric: item.value
            for item in getattr(snapshot, "facts", ())
            if getattr(item, "domain", None) == "intraday_research"
        }
        for timeframe in result:
            status = availability.get(f"intraday.{timeframe}", "MISSING")
            result[timeframe]["availability"] = status
            if status != "AVAILABLE":
                result[timeframe]["state"] = status
                continue
            trend = str(facts.get(f"intraday.{timeframe}.trend_structure") or "UNKNOWN").upper()
            location = str(facts.get(f"intraday.{timeframe}.price_location") or "UNKNOWN").upper()
            momentum = str(facts.get(f"intraday.{timeframe}.momentum") or "UNKNOWN").upper()
            if trend == "DOWN" and (location == "BELOW_FAST_SLOW" or momentum == "DOWN"):
                state = "WEAK"
            elif trend == "UP" and (location == "ABOVE_FAST_SLOW" or momentum == "UP"):
                state = "SUPPORTIVE"
            elif trend in {"UP", "FLAT"} and momentum != "DOWN":
                state = "NEUTRAL"
            else:
                state = "MIXED"
            result[timeframe]["state"] = state
        return result

    @staticmethod
    def _with_action(decision, action: str, reason_codes: tuple[str, ...]):
        if decision.prior_state == "FLAT":
            next_state = {"BUY": "ENTRY_PENDING", "WAIT": "FLAT", "BLOCKED": "BLOCKED"}[action]
        else:
            next_state = {
                "HOLD": "HOLDING",
                "ADD": "HOLDING",
                "REDUCE": "REDUCE_PENDING",
                "EXIT": "EXIT_PENDING",
                "BLOCKED": "BLOCKED",
            }[action]
        return decision.model_copy(update={
            "action": action,
            "next_state": next_state,
            "reason_codes": tuple(dict.fromkeys((*decision.reason_codes, *reason_codes))),
        })


__all__ = ["TimeframeAuthority", "TimeframeAuthorityPolicy"]
