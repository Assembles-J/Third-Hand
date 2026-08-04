"""Constrained DeepSeek evidence research with schema and reference validation."""
from __future__ import annotations

import json
import logging
import os
import re
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
        # The model is a constrained evidence interpreter, not an action engine:
        # it may choose only among candidates already produced by hard rules.
        run = {"run_id": str(uuid4()), "context_id": context.context_id, "input_hash": context.input_hash, "prompt_version": config.DECISION_RESEARCH_PROMPT_VERSION, "created_at": beijing_now().isoformat()}
        if not self.client.enabled:
            self.store.save_decision_ai_run({**run, "status": "skipped", "error_code": "not_configured", "payload": {}})
            logger.warning("Decision AI skipped context_id=%s symbol=%s code=not_configured", context.context_id, context.symbol)
            return DecisionAiOutcome(None, "skipped", "not_configured")
        messages = decision_research_messages(context, evidence, candidates)
        max_tokens = _decision_ai_max_tokens()
        for attempt in range(2):
            try:
                response = self.client.chat_json(messages, max_tokens=max_tokens, thinking=False)
                assessment = AiResearchAssessment.model_validate_json(_json_object(response.content))
                assessment = self._canonicalize_references(assessment, evidence)
                self._validate_references(assessment, evidence, candidates)
                self.store.save_decision_ai_run({**run, "status": "succeeded", "error_code": None, "model": response.model, "payload": assessment.model_dump(mode="json"), "metadata": {"response_id": response.response_id, "total_tokens": response.usage.total_tokens, "latency_ms": response.latency_ms}})
                logger.info("Decision AI succeeded context_id=%s symbol=%s model=%s latency_ms=%s tokens=%s", context.context_id, context.symbol, response.model, response.latency_ms, response.usage.total_tokens)
                return DecisionAiOutcome(assessment, "succeeded", model=response.model)
            except (LlmClientError, ValidationError, ValueError, json.JSONDecodeError) as error:
                if attempt == 0 and not isinstance(error, LlmClientError):
                    messages = [*messages, {"role": "user", "content": _repair_instruction(error, evidence, candidates)}]
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
        # Reject invented citations and invented actions before persisting model
        # output.  This keeps every visible AI claim traceable to the snapshot.
        known = {item.evidence_id for item in evidence}
        referenced = set(assessment.supporting_evidence_ids) | set(assessment.opposing_evidence_ids)
        referenced |= {item_id for step in assessment.reasoning_steps for item_id in step.evidence_ids}
        if unknown := referenced - known:
            raise ValueError(f"unknown evidence IDs: {sorted(unknown)}")
        allowed = {candidate.action for candidate in candidates}
        if assessment.preferred_action not in allowed:
            raise ValueError("AI action is not a policy candidate")

    @staticmethod
    def _canonicalize_references(assessment: AiResearchAssessment, evidence: tuple[EvidenceItem, ...]) -> AiResearchAssessment:
        """Accept a unique evidence title only when it maps unambiguously to supplied data.

        Some models occasionally quote an evidence title rather than its machine ID.
        Converting an exact, unique title keeps the citation traceable; all other values
        still go through the strict unknown-ID rejection below.
        """
        titles: dict[str, str | None] = {}
        for item in evidence:
            key = item.title.strip()
            titles[key] = item.evidence_id if key not in titles else None

        def canonicalize(reference: str) -> str:
            return titles.get(reference.strip()) or reference

        return assessment.model_copy(update={
            "supporting_evidence_ids": tuple(canonicalize(item) for item in assessment.supporting_evidence_ids),
            "opposing_evidence_ids": tuple(canonicalize(item) for item in assessment.opposing_evidence_ids),
            "reasoning_steps": tuple(
                step.model_copy(update={"evidence_ids": tuple(canonicalize(item) for item in step.evidence_ids)})
                for step in assessment.reasoning_steps
            ),
        })


def _json_object(content: str) -> str:
    """Allow a single Markdown JSON fence without accepting explanatory prose."""
    stripped = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    return fenced.group(1) if fenced else stripped


def _repair_instruction(error: Exception, evidence: tuple[EvidenceItem, ...], candidates: tuple[ActionCandidate, ...]) -> str:
    """Give the retry a concrete contract, rather than a generic invalid-output notice."""
    evidence_ids = ", ".join(item.evidence_id for item in evidence)
    actions = ", ".join(candidate.action for candidate in candidates)
    return (
        "Your previous JSON cannot be used: " + str(error) + ". Return ONE JSON object only, with no Markdown. "
        "Use exactly these keys: thesis_status, preferred_action, supporting_evidence_ids, opposing_evidence_ids, "
        "missing_evidence, reasoning_steps, rule_suggestions, uncertainty, summary. Every evidence ID must be copied exactly from this list "
        f"(or use []): [{evidence_ids}]. preferred_action must be one of: [{actions}]. "
        "Each reasoning_steps item must be {stage: evidence|conflict|uncertainty, summary: short plain Chinese, evidence_ids: [...]}."
    )


def _decision_ai_max_tokens() -> int:
    """Keep the structured response concise, while leaving room for evidence citations."""
    try:
        return min(max(int(os.getenv("DECISION_AI_MAX_TOKENS", "1200")), 700), 2400)
    except ValueError:
        logger.warning("DECISION_AI_MAX_TOKENS is invalid; using 1200")
        return 1200
