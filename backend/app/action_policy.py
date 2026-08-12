"""Deterministic action candidates for shadow analysis only."""
from __future__ import annotations

from app import decision_config as config
from app.decision_models import ActionCandidate, DecisionContext, EvidenceItem


class ActionPolicyEngine:
    """Apply hard-rule precedence without producing a live recommendation or size."""

    version = config.ACTION_POLICY_VERSION

    def evaluate(self, context: DecisionContext, evidence: tuple[EvidenceItem, ...]) -> tuple[ActionCandidate, ...]:
        # Precedence is deliberate: data-quality blocks first, then exit/risk
        # constraints, and only then add/open conditions.  AI cannot reorder it.
        by_id = {item.evidence_id: item for item in evidence}
        ids = set(by_id)
        if context.data_quality.status == "blocked":
            return (self._candidate("BLOCKED", 100, (), (), ("data_quality.blocked",), context.data_quality.missing_fields),)

        candidates: list[ActionCandidate] = []
        if self._reduce_ids(ids):
            support = tuple(sorted(self._reduce_ids(ids)))
            candidates.append(self._candidate("REDUCE", 85, support, (), ("position_or_risk.reduce",)))
        elif self._add_allowed(context, ids):
            candidates.append(self._candidate("ADD", 70, self._positive_ids(ids), (), ("signal.add",)))
        elif self._open_allowed(context, ids):
            candidates.append(self._candidate("OPEN", 65, self._positive_ids(ids), (), ("signal.open",)))
        elif context.position:
            candidates.append(self._candidate("HOLD", 40, (), (), ("default.hold",)))
        else:
            candidates.append(self._candidate("WATCH", 30, (), (), ("default.watch",)))

        # A missing user-authored plan, event enrichment, or relative-strength
        # comparison should lower confidence, not turn every whole-market paper
        # candidate into WATCH.  Quote, bars, risk, and portfolio inputs remain
        # the hard prerequisites for an autonomous simulated action.
        critical_degradation = ("daily_bars.minimum_60", "account.total_assets", "risk")
        has_critical_degradation = any(warning.startswith(critical_degradation) for warning in context.data_quality.warnings)
        if context.data_quality.status == "degraded" and candidates[0].action in {"ADD", "OPEN", "HOLD"} and has_critical_degradation:
            candidates.insert(0, self._candidate("WATCH", 60, ("data_quality.summary",), (), ("data_quality.degraded",), context.data_quality.warnings))
        return tuple(candidates[:3])

    @staticmethod
    def _candidate(action, priority, supporting, opposing, rules, blocked=()):
        return ActionCandidate(action=action, priority=priority, policy_score=priority / 100, supporting_evidence_ids=tuple(supporting), opposing_evidence_ids=tuple(opposing), triggered_rule_ids=tuple(rules), blocked_reasons=tuple(blocked))

    @staticmethod
    def _reduce_ids(ids: set[str]) -> set[str]:
        direct = {"position.above_max", "risk.historical_downside_high", "risk.annualized_volatility_high"}
        matched = ids.intersection(direct)
        bearish_event = any(item.startswith("event.negative.") for item in ids) and "trend.below_sma20_and_sma60" in ids
        defensive_weak = {"market.defensive", "relative.underperform_20d", "trend.below_sma20_and_sma60"}.issubset(ids)
        if bearish_event:
            matched.add("event.negative")
        if defensive_weak:
            matched.add("market.defensive")
        return matched

    @staticmethod
    def _add_allowed(context: DecisionContext, ids: set[str]) -> bool:
        position = context.position
        if not position or not context.quote or not context.risk:
            return False
        if context.account.available_cash <= 0 or any(item.startswith("event.negative.") for item in ids):
            return False
        if "trend.below_sma20_and_sma60" in ids or "market.defensive" in ids:
            return False
        return bool(ActionPolicyEngine._positive_ids(ids))

    @staticmethod
    def _open_allowed(context: DecisionContext, ids: set[str]) -> bool:
        return bool(not context.position and context.quote and context.risk and context.account.available_cash > 0 and ActionPolicyEngine._positive_ids(ids) and "market.defensive" not in ids)

    @staticmethod
    def _positive_ids(ids: set[str]) -> tuple[str, ...]:
        return tuple(sorted(ids.intersection({"trend.above_sma20", "trend.sma20_above_sma60", "market.supportive", "relative.outperform_20d"})))
