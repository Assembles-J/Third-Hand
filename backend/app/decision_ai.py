"""Constrained DeepSeek evidence research with schema and reference validation."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import uuid4

from pydantic import ValidationError

from app import decision_config as config
from app.decision_models import AiResearchAssessment, DecisionContext, EvidenceItem, ActionCandidate
from app.decision_prompts import decision_research_messages
from app.llm_client import DeepSeekClient, LlmClientError
from app.time_utils import beijing_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DecisionAiOutcome:
    assessment: AiResearchAssessment | None
    status: str
    error_code: str | None = None
    model: str | None = None


class DecisionAiService:
    def __init__(self, store, client: DeepSeekClient | None = None) -> None:
        self.store, self.client = store, client or DeepSeekClient()

    def assess(self, context: DecisionContext, evidence: tuple[EvidenceItem, ...], candidates: tuple[ActionCandidate, ...]) -> DecisionAiOutcome:
        run = {"run_id": str(uuid4()), "context_id": context.context_id, "input_hash": context.input_hash, "prompt_version": config.DECISION_RESEARCH_PROMPT_VERSION, "created_at": beijing_now().isoformat()}
        if not self.client.enabled:
            self.store.save_decision_ai_run({**run, "status": "skipped", "error_code": "not_configured", "payload": {}})
            logger.warning("Decision AI skipped context_id=%s symbol=%s code=not_configured", context.context_id, context.symbol)
            return DecisionAiOutcome(None, "skipped", "not_configured")
        messages = decision_research_messages(context, evidence, candidates)
        for attempt in range(2):
            try:
                response = self.client.chat_json(messages, max_tokens=700, thinking=False)
                assessment = AiResearchAssessment.model_validate_json(response.content)
                self._validate_references(assessment, evidence, candidates)
                self.store.save_decision_ai_run({**run, "status": "succeeded", "error_code": None, "model": response.model, "payload": assessment.model_dump(mode="json"), "metadata": {"response_id": response.response_id, "total_tokens": response.usage.total_tokens, "latency_ms": response.latency_ms}})
                logger.info("Decision AI succeeded context_id=%s symbol=%s model=%s latency_ms=%s tokens=%s", context.context_id, context.symbol, response.model, response.latency_ms, response.usage.total_tokens)
                return DecisionAiOutcome(assessment, "succeeded", model=response.model)
            except (LlmClientError, ValidationError, ValueError, json.JSONDecodeError) as error:
                if attempt == 0 and not isinstance(error, LlmClientError):
                    messages = [*messages, {"role": "user", "content": "Previous output was invalid. Return the required JSON with only allowed action and known evidence IDs."}]
                    continue
                code = error.code if isinstance(error, LlmClientError) else "invalid_ai_output"
                status_code = error.status_code if isinstance(error, LlmClientError) else None
                model = getattr(getattr(self.client, "settings", None), "model", None)
                self.store.save_decision_ai_run({**run, "status": "failed", "error_code": code, "payload": {}, "metadata": {"model": model, "status_code": status_code}})
                logger.warning("Decision AI failed context_id=%s symbol=%s model=%s code=%s status=%s error_type=%s", context.context_id, context.symbol, model, code, status_code, type(error).__name__)
                return DecisionAiOutcome(None, "failed", code, model)

        return DecisionAiOutcome(None, "failed", "unknown")

    @staticmethod
    def _validate_references(assessment, evidence, candidates) -> None:
        known = {item.evidence_id for item in evidence}
        referenced = set(assessment.supporting_evidence_ids) | set(assessment.opposing_evidence_ids)
        referenced |= {item_id for step in assessment.reasoning_steps for item_id in step.evidence_ids}
        if unknown := referenced - known:
            raise ValueError(f"unknown evidence IDs: {sorted(unknown)}")
        allowed = {candidate.action for candidate in candidates}
        if assessment.preferred_action not in allowed:
            raise ValueError("AI action is not a policy candidate")
