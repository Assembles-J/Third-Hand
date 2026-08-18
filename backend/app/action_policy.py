"""Deterministic action candidates and explainable formal gate diagnostics."""
from __future__ import annotations

from app import decision_config as config
from app.decision_models import ActionCandidate, DecisionContext, EvidenceItem


class ActionPolicyEngine:
    """Apply hard-rule precedence using POLICY-scoped evidence only."""

    version = config.ACTION_POLICY_VERSION

    def evaluate(self, context: DecisionContext, evidence: tuple[EvidenceItem, ...]) -> tuple[ActionCandidate, ...]:
        # Research-only and audit-only evidence must never influence formal
        # actions. This structural filter is the policy boundary: upstream
        # labels can change without granting news, fund flow or LLM output
        # trading authority.
        policy_evidence = tuple(item for item in evidence if item.usage_scope == "POLICY")
        by_id = {item.evidence_id: item for item in policy_evidence}
        ids = set(by_id)
        if context.data_quality.status == "blocked":
            return (self._candidate("BLOCKED", 100, (), (), ("data_quality.blocked",), context.data_quality.missing_fields),)

        candidates: list[ActionCandidate] = []
        consistency_conflicted = any(
            warning.startswith("consistency.")
            for warning in context.data_quality.warnings
        )
        # REDUCE is a position-management verb. Risk evidence may block a new
        # position, but an empty account can never formally reduce something it
        # does not own. Cross-source contradictions also suppress executable
        # position changes: a stale quote must not manufacture a position-cap
        # breach against newer daily/technical inputs.
        if context.position and not consistency_conflicted and self._reduce_ids(ids):
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

        critical_degradation = ("daily_bars.minimum_60", "account.total_assets", "risk")
        has_critical_degradation = any(warning.startswith(critical_degradation) for warning in context.data_quality.warnings)
        if context.data_quality.status == "degraded" and candidates[0].action in {"ADD", "OPEN", "HOLD"} and has_critical_degradation:
            candidates.insert(0, self._candidate("WATCH", 60, ("data_quality.summary",), (), ("data_quality.degraded",), context.data_quality.warnings))
        return tuple(candidates[:3])

    def open_gate_audit(self, context: DecisionContext, evidence: tuple[EvidenceItem, ...]) -> dict[str, object]:
        """Explain the existing OPEN rule without changing or scoring it.

        The audit is intentionally deterministic and POLICY-only. It answers
        whether an empty-account candidate *could* OPEN under the frozen formal
        rule, and if not, which exact precondition is missing. It is diagnostics,
        not a new opportunity score and not AI authority.
        """
        policy_ids = {
            item.evidence_id
            for item in evidence
            if item.usage_scope == "POLICY"
        }
        positive = self._positive_ids(policy_ids)
        gate = next(
            (item for item in context.data_quality.action_gates if item.action == "OPEN"),
            None,
        )
        gate_allowed = bool(gate and gate.permission == "allowed")

        checks: list[dict[str, object]] = []
        blockers: list[str] = []

        def add(check_id: str, passed: bool, detail: str, *, evidence_ids=()) -> None:
            checks.append({
                "check_id": check_id,
                "passed": bool(passed),
                "detail": detail,
                "evidence_ids": list(evidence_ids),
            })
            if not passed:
                blockers.append(detail)

        gate_detail = "OPEN action gate allowed"
        if not gate_allowed:
            reasons = list(gate.reasons) if gate else ["OPEN action gate missing"]
            unavailable = list(gate.unavailable_fields) if gate else []
            suffix = "; ".join([*reasons, *(f"unavailable:{item}" for item in unavailable)])
            gate_detail = f"OPEN action gate blocked: {suffix}" if suffix else "OPEN action gate blocked"
        add("action_gate.open", gate_allowed, gate_detail)
        add("position.absent", context.position is None, "existing position blocks OPEN; use HOLD/ADD/REDUCE semantics")
        add("quote.available", context.quote is not None, "quote unavailable")
        add("risk.available", context.risk is not None, "risk unavailable")
        add("cash.positive", context.account.available_cash > 0, "available cash is not positive")
        add(
            "positive_policy_evidence.present",
            bool(positive),
            "no positive POLICY evidence for OPEN",
            evidence_ids=positive,
        )
        add(
            "market.not_defensive",
            "market.defensive" not in policy_ids,
            "market.defensive blocks OPEN",
            evidence_ids=("market.defensive",) if "market.defensive" in policy_ids else (),
        )

        permission = "allowed" if all(bool(item["passed"]) for item in checks) else "blocked"
        return {
            "permission": permission,
            "checks": checks,
            "positive_evidence_ids": list(positive),
            "blockers": list(dict.fromkeys(blockers)),
            "policy_version": self.version,
            "diagnostic_only": True,
        }

    @staticmethod
    def _candidate(action, priority, supporting, opposing, rules, blocked=()):
        return ActionCandidate(action=action, priority=priority, policy_score=priority / 100, supporting_evidence_ids=tuple(supporting), opposing_evidence_ids=tuple(opposing), triggered_rule_ids=tuple(rules), blocked_reasons=tuple(blocked))

    @staticmethod
    def _reduce_ids(ids: set[str]) -> set[str]:
        # A static risk label describes the conditions accepted at entry; it is
        # not evidence that those conditions deteriorated after entry. Letting
        # it directly REDUCE only when a position exists creates the invalid
        # FLAT -> BUY -> HOLDING -> REDUCE loop on the identical snapshot.
        # Baseline risk remains visible to deterministic sizing. A future risk
        # reduction trigger must be an explicit deterioration or threshold
        # crossing with its own point-in-time evidence and policy version.
        # Deliberately excludes event/news/research evidence as well.
        direct = {"position.above_max"}
        matched = ids.intersection(direct)
        defensive_weak = {"market.defensive", "relative.underperform_20d", "trend.below_sma20_and_sma60"}.issubset(ids)
        if defensive_weak:
            matched.add("market.defensive")
        return matched

    @staticmethod
    def _add_allowed(context: DecisionContext, ids: set[str]) -> bool:
        position = context.position
        if ActionPolicyEngine._gate(context, "ADD") != "allowed":
            return False
        if not position or not context.quote or not context.risk:
            return False
        if context.account.available_cash <= 0:
            return False
        if (
            "trend.below_sma20_and_sma60" in ids
            or "market.defensive" in ids
            or ActionPolicyEngine._static_risk_ids(ids)
        ):
            return False
        return bool(ActionPolicyEngine._positive_ids(ids))

    @staticmethod
    def _static_risk_ids(ids: set[str]) -> set[str]:
        """Baseline risk constrains new/incremental risk, never causes a sell."""
        return ids.intersection({"risk.historical_downside_high", "risk.annualized_volatility_high"})

    def _open_allowed(self, context: DecisionContext, ids: set[str]) -> bool:
        # Keep the formal predicate in lock-step with the audit checks. The
        # synthetic EvidenceItems are unnecessary here, so retain the compact
        # predicate while tests assert parity with open_gate_audit.
        if self._gate(context, "OPEN") != "allowed":
            return False
        return bool(
            not context.position
            and context.quote
            and context.risk
            and context.account.available_cash > 0
            and self._positive_ids(ids)
            and "market.defensive" not in ids
        )

    @staticmethod
    def _gate(context: DecisionContext, action: str) -> str:
        return next((gate.permission for gate in context.data_quality.action_gates if gate.action == action), "blocked")

    @staticmethod
    def _positive_ids(ids: set[str]) -> tuple[str, ...]:
        return tuple(sorted(ids.intersection({"trend.above_sma20", "trend.sma20_above_sma60", "market.supportive", "relative.outperform_20d"})))
