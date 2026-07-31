"""End-to-end auditable decision orchestration; never executes trades."""
from __future__ import annotations

from uuid import uuid4

from app import decision_config as config
from app.decision_models import DecisionReport
from app.time_utils import beijing_now


class DecisionOrchestrator:
    def __init__(self, evidence_engine, policy_engine, sizing_engine, ai_service, guard) -> None:
        self.evidence_engine, self.policy_engine = evidence_engine, policy_engine
        self.sizing_engine, self.ai_service, self.guard = sizing_engine, ai_service, guard

    def generate(self, context) -> DecisionReport:
        evidence = self.evidence_engine.build(context)
        candidates = self.policy_engine.evaluate(context, evidence)
        assessment = self.ai_service.assess(context, evidence, candidates) if config.DECISION_AI_ENABLED else None
        assessment = self.guard.guard(candidates, assessment)
        action = candidates[0].action
        sizing = self.sizing_engine.size(context, action) if config.DECISION_SIZING_ENABLED else None
        status = "BLOCKED" if context.data_quality.status == "blocked" else "DEGRADED" if context.data_quality.status == "degraded" else "READY"
        return DecisionReport(decision_id=str(uuid4()), context_id=context.context_id, symbol=context.symbol, generated_at=beijing_now(), status=status, action=action, summary=f"Deterministic policy selected {action} from {len(candidates)} candidate(s).", evidence=evidence, action_candidates=candidates, ai_assessment=assessment, sizing=sizing, policy_version=self.policy_engine.version, prompt_version=config.DECISION_RESEARCH_PROMPT_VERSION if assessment else None, input_hash=context.input_hash)
