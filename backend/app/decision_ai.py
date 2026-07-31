"""Constrained DeepSeek evidence research with schema and reference validation."""
from __future__ import annotations

import json
from uuid import uuid4

from pydantic import ValidationError

from app import decision_config as config
from app.decision_models import AiResearchAssessment, DecisionContext, EvidenceItem, ActionCandidate
from app.decision_prompts import decision_research_messages
from app.llm_client import DeepSeekClient, LlmClientError
from app.time_utils import beijing_now


class DecisionAiService:
    def __init__(self, store, client: DeepSeekClient | None = None) -> None:
        self.store, self.client = store, client or DeepSeekClient()

    def assess(self, context: DecisionContext, evidence: tuple[EvidenceItem, ...], candidates: tuple[ActionCandidate, ...]) -> AiResearchAssessment | None:
        run = {"run_id": str(uuid4()), "context_id": context.context_id, "input_hash": context.input_hash, "prompt_version": config.DECISION_RESEARCH_PROMPT_VERSION, "created_at": beijing_now().isoformat()}
        if not self.client.enabled:
            self.store.save_decision_ai_run({**run, "status": "skipped", "error_code": "not_configured", "payload": {}})
            return None
        messages = decision_research_messages(context, evidence, candidates)
        for attempt in range(2):
            try:
                response = self.client.chat_json(messages, max_tokens=700, thinking=False)
                assessment = AiResearchAssessment.model_validate_json(response.content)
                self._validate_references(assessment, evidence, candidates)
                self.store.save_decision_ai_run({**run, "status": "succeeded", "error_code": None, "model": response.model, "payload": assessment.model_dump(mode="json"), "metadata": {"response_id": response.response_id, "total_tokens": response.usage.total_tokens, "latency_ms": response.latency_ms}})
                return assessment
            except (LlmClientError, ValidationError, ValueError, json.JSONDecodeError) as error:
                if attempt == 0 and not isinstance(error, LlmClientError):
                    messages = [*messages, {"role": "user", "content": "Previous output was invalid. Return the required JSON with only allowed action and known evidence IDs."}]
                    continue
                code = error.code if isinstance(error, LlmClientError) else "invalid_ai_output"
                self.store.save_decision_ai_run({**run, "status": "failed", "error_code": code, "payload": {}, "metadata": {}})
                return None

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
