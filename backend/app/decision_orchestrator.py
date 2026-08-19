"""End-to-end auditable decision orchestration; never executes trades."""
from __future__ import annotations

import logging
from uuid import uuid4

from app import decision_config as config
from app.application_services.strategy import swing_v1_profile
from app.atomic_evidence import AtomicEvidenceSnapshotBuilder
from app.canonical_snapshot import build_canonical_market_snapshot
from app.decision_ai import DecisionAiOutcome
from app.decision_models import DecisionReport, OperationItem
from app.research_assessment import ResearchAggregator, SemanticInvariantValidator
from app.decision_semantics import DecisionArbiter
from app.decision_continuity import DecisionContinuityPolicy
from app.timeframe_authority import TimeframeAuthorityPolicy
from app.time_utils import beijing_now
from app.trading_calendar import TradingCalendarService

logger = logging.getLogger(__name__)


class DecisionOrchestrator:
    def __init__(self, evidence_engine, policy_engine, sizing_engine, ai_service, guard, atomic_evidence_builder=None, research_aggregator=None, research_validator=None, decision_arbiter=None, timeframe_policy=None, prior_report_loader=None, continuity_policy=None, strategy_profile=None) -> None:
        self.evidence_engine, self.policy_engine = evidence_engine, policy_engine
        self.sizing_engine, self.ai_service, self.guard = sizing_engine, ai_service, guard
        self.atomic_evidence_builder = atomic_evidence_builder or AtomicEvidenceSnapshotBuilder()
        self.research_aggregator = research_aggregator or ResearchAggregator()
        self.research_validator = research_validator or SemanticInvariantValidator()
        self.decision_arbiter = decision_arbiter or DecisionArbiter()
        self.timeframe_policy = timeframe_policy or TimeframeAuthorityPolicy()
        self.prior_report_loader = prior_report_loader
        self.continuity_policy = continuity_policy or DecisionContinuityPolicy()
        self.strategy_profile = strategy_profile or swing_v1_profile(
            action_policy_version=str(self.policy_engine.version),
            timeframe_policy_version=str(
                getattr(self.timeframe_policy, "version", config.TIMEFRAME_AUTHORITY_POLICY_VERSION)
            ),
        )

    def generate(self, context, *, candidate_audit: dict[str, object] | None = None) -> DecisionReport:
        evidence = self.evidence_engine.build(context)
        # ActionPolicy consumes only EvidenceItems. Atomic Evidence is built
        # after candidates freeze; its deterministic aggregate may only veto a
        # sufficiently evidenced adverse BUY/ADD, and it supplies the AI prompt.
        candidates = self.policy_engine.evaluate(context, evidence)
        atomic_evidence_shadow = self.atomic_evidence_builder.build(context, evidence)
        research_assessment = self.research_aggregator.build(atomic_evidence_shadow)
        research_validation = self.research_validator.validate(atomic_evidence_shadow, research_assessment)
        if not research_validation.valid:
            raise ValueError(f"invalid deterministic research assessment: {research_validation.violations}")
        semantic_decision = self.decision_arbiter.arbitrate(
            context,
            candidates,
            research_assessment=research_assessment,
        )

        # Multi-timeframe policy is one deterministic refinement inside the
        # existing authority chain. It can only downgrade new risk (BUY->WAIT,
        # ADD->HOLD); it cannot manufacture BUY/ADD or lower-timeframe exits.
        timeframe_material_state: dict[str, object] = {}
        apply_timeframes = getattr(self.timeframe_policy, "apply", None)
        if callable(apply_timeframes):
            semantic_decision, timeframe_authority, timeframe_material_state = apply_timeframes(
                context,
                atomic_evidence_shadow,
                semantic_decision,
            )
        else:
            # Compatibility for injected legacy/test policies that expose only
            # the descriptive `assess(context)` contract.
            timeframe_authority = self.timeframe_policy.assess(context)

        # Continuity sees only the approved discrete timeframe policy state,
        # never raw bars/timestamps. A confirmation-state transition may unlock
        # a new recommendation; ordinary intraday refreshes may not.
        prior_report = self.prior_report_loader(context.symbol) if self.prior_report_loader else None
        formal_action, decision_memory = self.continuity_policy.assess(
            context,
            semantic_decision.action,
            prior_report,
            research_assessment,
            timeframe_state=timeframe_material_state,
        )
        if formal_action != semantic_decision.action:
            semantic_decision = self._with_continuity_action(semantic_decision, formal_action)

        logger.info(
            "Atomic evidence snapshot context_id=%s symbol=%s snapshot_hash=%s fact_count=%s availability_count=%s conflict_count=%s",
            context.context_id,
            context.symbol,
            atomic_evidence_shadow.snapshot_hash,
            len(atomic_evidence_shadow.facts),
            len(atomic_evidence_shadow.availability),
            len(atomic_evidence_shadow.conflicts),
        )
        canonical = self._canonical_market(context)
        if config.DECISION_AI_ENABLED:
            logger.info(
                "Decision AI dispatch context_id=%s symbol=%s evidence_count=%s candidate_actions=%s",
                context.context_id,
                context.symbol,
                len(evidence),
                ",".join(candidate.action for candidate in candidates),
            )
            ai_outcome = self.ai_service.assess(context, evidence, candidates, atomic_evidence=atomic_evidence_shadow)
        else:
            logger.warning(
                "Decision AI disabled context_id=%s symbol=%s code=feature_disabled",
                context.context_id,
                context.symbol,
            )
            ai_outcome = DecisionAiOutcome(None, "disabled", "feature_disabled")
        assessment = self.guard.guard(candidates, ai_outcome.assessment)
        action = self._legacy_action(formal_action)
        ai_shadow_action = assessment.preferred_action if assessment else None
        sizing = self.sizing_engine.size(context, action) if config.DECISION_SIZING_ENABLED else None
        status = "BLOCKED" if context.data_quality.status == "blocked" else "DEGRADED" if context.data_quality.status == "degraded" else "READY"
        candidate_audit = candidate_audit or {}
        market_as_of = self._display_as_of(context, canonical.display_price_source)
        market_change = (
            context.quote.change_percent
            if context.quote and canonical.display_price_source == "quote"
            else None
        )
        execution_eligible_after = (
            context.quote.as_of
            if context.quote and canonical.execution_price is not None
            else None
        )
        return DecisionReport(
            decision_id=str(uuid4()), context_id=context.context_id, symbol=context.symbol,
            name=context.name, generated_at=beijing_now(), status=status, action=action,
            summary=self._summary(action, candidates[0].blocked_reasons), data_quality=context.data_quality,
            evidence=evidence, atomic_evidence_shadow=atomic_evidence_shadow,
            research_assessment=research_assessment,
            research_assessment_validation=research_validation,
            entry_decision=semantic_decision if context.position is None else None,
            position_decision=semantic_decision if context.position is not None else None,
            formal_action=formal_action,
            decision_memory=decision_memory,
            timeframe_authority=timeframe_authority,
            strategy=self.strategy_profile,
            action_candidates=candidates,
            operation_items=self._operation_items(context, action, candidates[0].blocked_reasons, sizing, canonical.display_price),
            ai_assessment=assessment, ai_status=ai_outcome.status, ai_error_code=ai_outcome.error_code,
            ai_shadow_action=ai_shadow_action,
            ai_shadow_agreement=(ai_shadow_action == action) if ai_shadow_action is not None else None,
            market_price=canonical.display_price,
            market_change_percent=market_change,
            market_as_of=market_as_of,
            sizing=sizing, policy_version=self.policy_engine.version,
            prompt_version=config.DECISION_RESEARCH_PROMPT_VERSION if assessment else None,
            audit_versions=config.audit_version_snapshot(),
            candidate_selection_version=candidate_audit.get("candidate_selection_version"),
            candidate_pool_hash=candidate_audit.get("candidate_pool_hash"),
            candidate_rotation_key=candidate_audit.get("candidate_rotation_key"),
            candidate_rank=candidate_audit.get("candidate_rank"),
            candidate_selection_reason=candidate_audit.get("candidate_selection_reason"),
            execution_eligible_after=execution_eligible_after,
            model=ai_outcome.model, input_hash=context.input_hash,
        )

    @staticmethod
    def _canonical_market(context):
        market = (
            context.instrument.market
            if context.instrument
            else TradingCalendarService.market_for_symbol(context.symbol)
        )
        return build_canonical_market_snapshot(
            market=market,
            quote_price=context.quote.price if context.quote else None,
            quote_as_of=context.quote.as_of if context.quote else None,
            quote_retrieved_at=context.quote.retrieved_at if context.quote else None,
            daily_close=context.daily_bars.last_close,
            daily_bar_as_of=context.daily_bars.last_trading_date,
            risk_as_of=context.risk.as_of if context.risk else None,
        )

    @staticmethod
    def _display_as_of(context, display_source: str) -> str | None:
        if display_source in {"quote", "stale_quote"}:
            return context.quote.as_of if context.quote else None
        if display_source in {"daily_close", "stale_daily_close"}:
            return context.daily_bars.last_trading_date
        return None

    @staticmethod
    def _operation_items(context, action, candidate_blockers, sizing, reference_price) -> tuple[OperationItem, ...]:
        sizing_blockers = tuple(sizing.blocked_reasons) if sizing else ()
        blockers = tuple(dict.fromkeys((*candidate_blockers, *sizing_blockers)))
        if blockers:
            return (OperationItem(kind="COMPLETE", title="先补全执行条件", trigger="完成下列必填项后重新生成工作台", status="needs_input", blockers=blockers),)
        title_by_action = {"OPEN": "建立仓位", "ADD": "满足条件后加仓", "REDUCE": "满足条件后减仓", "EXIT": "满足条件后退出", "HOLD": "继续持有", "WATCH": "继续观察"}
        trigger = "以当前行情为准；下单前复核价格、数量与风险边界。" if action in {"OPEN", "ADD", "REDUCE", "EXIT"} else "当前无待执行交易；等待新的行情、公告或风险信号。"
        return (OperationItem(
            kind=action,
            title=title_by_action.get(action, "暂不操作"),
            trigger=trigger,
            reference_price=reference_price,
            invalidation_price=getattr(sizing, "invalidation_price", None),
            suggested_quantity=getattr(sizing, "suggested_quantity", None),
            target_quantity=getattr(sizing, "target_quantity", None),
            status="ready",
        ),)

    @staticmethod
    def _legacy_action(formal_action: str) -> str:
        return {
            "BUY": "OPEN", "WAIT": "WATCH", "HOLD": "HOLD", "ADD": "ADD",
            "REDUCE": "REDUCE", "EXIT": "EXIT", "BLOCKED": "BLOCKED",
        }[formal_action]

    @staticmethod
    def _with_continuity_action(decision, formal_action: str):
        if decision.prior_state == "FLAT":
            next_state = {"BUY": "ENTRY_PENDING", "WAIT": "FLAT", "BLOCKED": "BLOCKED"}[formal_action]
        else:
            next_state = {
                "HOLD": "HOLDING", "ADD": "HOLDING", "REDUCE": "REDUCE_PENDING",
                "EXIT": "EXIT_PENDING", "BLOCKED": "BLOCKED",
            }[formal_action]
        return decision.model_copy(update={
            "action": formal_action,
            "next_state": next_state,
            "reason_codes": tuple(dict.fromkeys((*decision.reason_codes, "continuity.no_material_change"))),
        })

    @staticmethod
    def _summary(action, blocked_reasons) -> str:
        if action == "BLOCKED":
            return "关键输入尚未齐备，暂不生成操作结论。请完成“解除阻断”中的项目后重新分析。"
        labels = {
            "OPEN": "已形成建立仓位候选，仍需核验计划条件和风险约束。",
            "ADD": "已形成加仓候选，仍需遵守仓位和风险约束。",
            "HOLD": "当前规则倾向持有，继续跟踪关键证据和交易计划条件。",
            "WATCH": "当前以观察为主，等待数据或交易计划条件进一步确认。",
            "REDUCE": "风险或仓位证据触发复核，建议结合交易计划审查减仓条件。",
            "EXIT": "退出条件触发复核，建议核验交易计划与最新事实后处理。",
        }
        return labels.get(action, "本次报告已生成，请结合证据和数据状态进行复核。")
