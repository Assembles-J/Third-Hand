"""Constrained DeepSeek evidence research with schema and reference validation."""
from __future__ import annotations

import hashlib
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
from app.model_policy import ModelPolicy
from app.time_utils import beijing_now

logger = logging.getLogger(__name__)

DECISION_AI_RUNTIME_AUDIT_VERSION = "decision-ai-runtime-audit-v2-policy-attempt-lineage"


@dataclass(frozen=True)
class DecisionAiOutcome:
    assessment: AiResearchAssessment | None
    status: str
    error_code: str | None = None
    model: str | None = None


class DecisionAiService:
    def __init__(self, store, client: DeepSeekClient | None = None, model_policy: ModelPolicy | None = None) -> None:
        self.store, self.client = store, client or DeepSeekClient()
        self.model_policy = model_policy or ModelPolicy()

    def assess(self, context: DecisionContext, evidence: tuple[EvidenceItem, ...], candidates: tuple[ActionCandidate, ...], *, atomic_evidence=None) -> DecisionAiOutcome:
        # The model is a constrained evidence interpreter, not an action engine:
        # it may choose only among candidates already produced by hard rules.
        run = {
            "run_id": str(uuid4()),
            "context_id": context.context_id,
            "input_hash": context.input_hash,
            "prompt_version": config.DECISION_RESEARCH_PROMPT_VERSION,
            "created_at": beijing_now().isoformat(),
        }
        settings = getattr(self.client, "settings", None)
        reasoning_model = getattr(settings, "reasoning_model", None)
        selection = self.model_policy.select(
            atomic_evidence,
            default_model=getattr(settings, "model", None),
            reasoning_model=reasoning_model,
            default_max_tokens=_decision_ai_max_tokens(),
        )
        evidence_hash = atomic_evidence.snapshot_hash if atomic_evidence is not None else _hash_json([
            item.model_dump(mode="json") for item in evidence
        ])
        if not self.client.enabled:
            self.store.save_decision_ai_run({
                **run,
                "status": "skipped",
                "error_code": "not_configured",
                "payload": {},
                "metadata": self._audit_metadata(
                    selection,
                    evidence_hash=evidence_hash,
                    retry_path=(),
                    policy_attempts=(),
                ),
            })
            logger.warning("Decision AI skipped context_id=%s symbol=%s code=not_configured", context.context_id, context.symbol)
            return DecisionAiOutcome(None, "skipped", "not_configured")

        messages = decision_research_messages(context, evidence, candidates, atomic_evidence=atomic_evidence)
        prompt_hash = _hash_json(messages)
        retry_path: list[dict[str, object]] = []
        policy_attempts: list[dict[str, object]] = []

        # The recovery graph is deliberately finite and auditable:
        # Flash -> Pro thinking -> Pro non-thinking structured. Provider retries
        # happen inside one client call and are recorded separately from these
        # policy-level attempts.
        for attempt_index in range(3):
            policy_attempt = {
                "policy_attempt": attempt_index + 1,
                "tier": selection.tier,
                "selected_model": selection.model,
                "thinking": selection.thinking,
                "max_tokens": selection.max_tokens,
                "prompt_hash": prompt_hash,
            }
            response = None
            try:
                response = self.client.chat_json(
                    messages,
                    model=selection.model,
                    max_tokens=selection.max_tokens,
                    thinking=selection.thinking,
                )
            except LlmClientError as error:
                policy_attempt.update(_provider_error_audit(error))
                policy_attempt["outcome"] = "provider_error"
                policy_attempt["validation_stage"] = "not_reached"
                recovery_reason = error.code if error.code in {"output_truncated", "empty_content"} else None
                if attempt_index < 2 and recovery_reason:
                    next_selection = self.model_policy.recover(
                        selection,
                        reason=recovery_reason,
                        reasoning_model=reasoning_model,
                    )
                    if next_selection != selection:
                        transition = {
                            "attempt": attempt_index + 1,
                            "reason": recovery_reason,
                            "error_type": type(error).__name__,
                            "from_tier": selection.tier,
                            "to_tier": next_selection.tier,
                        }
                        policy_attempt["transition_reason"] = recovery_reason
                        policy_attempt["next_tier"] = next_selection.tier
                        policy_attempts.append(policy_attempt)
                        retry_path.append(transition)
                        selection = next_selection
                        continue

                policy_attempt["final_fail_closed_reason"] = error.code
                policy_attempts.append(policy_attempt)
                retry_path.append({
                    "attempt": attempt_index + 1,
                    "reason": error.code,
                    "error_type": type(error).__name__,
                })
                self._save_failure(
                    run,
                    selection,
                    evidence_hash=evidence_hash,
                    prompt_hash=prompt_hash,
                    retry_path=retry_path,
                    policy_attempts=policy_attempts,
                    code=error.code,
                    status_code=error.status_code,
                    model=selection.model,
                    provider_retry_codes=list(error.retry_codes),
                    final_reason=error.code,
                )
                logger.warning(
                    "Decision AI failed context_id=%s symbol=%s model=%s code=%s status=%s error_type=%s",
                    context.context_id,
                    context.symbol,
                    selection.model,
                    error.code,
                    error.status_code,
                    type(error).__name__,
                )
                return DecisionAiOutcome(None, "failed", error.code, selection.model)

            # Provider call succeeded. Record its non-sensitive response lineage
            # before schema/semantic validation so a later failure cannot erase it.
            policy_attempt.update(_provider_success_audit(response))
            try:
                assessment = AiResearchAssessment.model_validate_json(_json_object(response.content))
            except (ValidationError, json.JSONDecodeError, ValueError) as error:
                return_or_continue = self._handle_validation_failure(
                    error=error,
                    validation_stage="schema",
                    context=context,
                    evidence=evidence,
                    candidates=candidates,
                    run=run,
                    selection=selection,
                    reasoning_model=reasoning_model,
                    evidence_hash=evidence_hash,
                    messages=messages,
                    prompt_hash=prompt_hash,
                    retry_path=retry_path,
                    policy_attempts=policy_attempts,
                    policy_attempt=policy_attempt,
                    attempt_index=attempt_index,
                )
                if isinstance(return_or_continue, DecisionAiOutcome):
                    return return_or_continue
                selection, messages, prompt_hash = return_or_continue
                continue

            assessment = self._canonicalize_references(assessment, evidence)
            try:
                self._validate_references(assessment, evidence, candidates)
            except ValueError as error:
                return_or_continue = self._handle_validation_failure(
                    error=error,
                    validation_stage="semantic",
                    context=context,
                    evidence=evidence,
                    candidates=candidates,
                    run=run,
                    selection=selection,
                    reasoning_model=reasoning_model,
                    evidence_hash=evidence_hash,
                    messages=messages,
                    prompt_hash=prompt_hash,
                    retry_path=retry_path,
                    policy_attempts=policy_attempts,
                    policy_attempt=policy_attempt,
                    attempt_index=attempt_index,
                )
                if isinstance(return_or_continue, DecisionAiOutcome):
                    return return_or_continue
                selection, messages, prompt_hash = return_or_continue
                continue

            policy_attempt.update({
                "outcome": "succeeded",
                "validation_stage": "schema_and_semantic",
                "validation_result": "passed",
            })
            policy_attempts.append(policy_attempt)
            self.store.save_decision_ai_run({
                **run,
                "status": "succeeded",
                "error_code": None,
                "model": response.model,
                "payload": assessment.model_dump(mode="json"),
                "metadata": {
                    **self._audit_metadata(
                        selection,
                        evidence_hash=evidence_hash,
                        retry_path=tuple(retry_path),
                        policy_attempts=tuple(policy_attempts),
                    ),
                    "prompt_hash": prompt_hash,
                    # Backward-compatible hash of the accepted structured payload.
                    "content_hash": _hash_json(assessment.model_dump(mode="json")),
                    "response_id": response.response_id,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "latency_ms": response.latency_ms,
                    "provider_attempt_count": response.attempt_count,
                    "provider_retry_codes": list(response.retry_codes),
                    "finish_reason": response.finish_reason,
                    "reasoning_present": response.reasoning_present,
                    "reasoning_length": response.reasoning_length,
                    "reasoning_hash": response.reasoning_hash,
                    "validation": "schema_and_semantic_passed",
                },
            })
            logger.info(
                "Decision AI succeeded context_id=%s symbol=%s model=%s latency_ms=%s tokens=%s",
                context.context_id,
                context.symbol,
                response.model,
                response.latency_ms,
                response.usage.total_tokens,
            )
            return DecisionAiOutcome(assessment, "succeeded", model=response.model)

        return DecisionAiOutcome(None, "failed", "unknown")

    def _handle_validation_failure(
        self,
        *,
        error: Exception,
        validation_stage: str,
        context,
        evidence,
        candidates,
        run,
        selection,
        reasoning_model,
        evidence_hash,
        messages,
        prompt_hash,
        retry_path,
        policy_attempts,
        policy_attempt,
        attempt_index: int,
    ):
        failure = _validation_failure_audit(error, validation_stage)
        policy_attempt.update({
            "outcome": "validation_failed",
            "validation_stage": validation_stage,
            **failure,
        })
        recovery_reason = "schema_or_semantic_validation_failed"
        if attempt_index < 2:
            next_selection = self.model_policy.recover(
                selection,
                reason=recovery_reason,
                reasoning_model=reasoning_model,
            )
            if next_selection != selection:
                transition = {
                    "attempt": attempt_index + 1,
                    "reason": recovery_reason,
                    "error_type": type(error).__name__,
                    "validation_stage": validation_stage,
                    "from_tier": selection.tier,
                    "to_tier": next_selection.tier,
                }
                policy_attempt["transition_reason"] = recovery_reason
                policy_attempt["next_tier"] = next_selection.tier
                policy_attempts.append(policy_attempt)
                retry_path.append(transition)
                repaired_messages = [
                    *messages,
                    {"role": "user", "content": _repair_instruction(error, evidence, candidates)},
                ]
                return next_selection, repaired_messages, _hash_json(repaired_messages)

        policy_attempt["final_fail_closed_reason"] = "invalid_ai_output"
        policy_attempts.append(policy_attempt)
        retry_path.append({
            "attempt": attempt_index + 1,
            "reason": "invalid_ai_output",
            "error_type": type(error).__name__,
            "validation_stage": validation_stage,
        })
        self._save_failure(
            run,
            selection,
            evidence_hash=evidence_hash,
            prompt_hash=prompt_hash,
            retry_path=retry_path,
            policy_attempts=policy_attempts,
            code="invalid_ai_output",
            status_code=None,
            model=selection.model,
            provider_retry_codes=[],
            final_reason=f"{validation_stage}_validation_failed",
        )
        logger.warning(
            "Decision AI failed context_id=%s symbol=%s model=%s code=invalid_ai_output validation_stage=%s error_type=%s",
            context.context_id,
            context.symbol,
            selection.model,
            validation_stage,
            type(error).__name__,
        )
        return DecisionAiOutcome(None, "failed", "invalid_ai_output", selection.model)

    def _save_failure(
        self,
        run,
        selection,
        *,
        evidence_hash,
        prompt_hash,
        retry_path,
        policy_attempts,
        code,
        status_code,
        model,
        provider_retry_codes,
        final_reason,
    ) -> None:
        self.store.save_decision_ai_run({
            **run,
            "status": "failed",
            "error_code": code,
            "payload": {},
            "metadata": {
                **self._audit_metadata(
                    selection,
                    evidence_hash=evidence_hash,
                    retry_path=tuple(retry_path),
                    policy_attempts=tuple(policy_attempts),
                ),
                "prompt_hash": prompt_hash,
                "model": model,
                "status_code": status_code,
                "provider_retry_codes": provider_retry_codes,
                "validation": "failed",
                "final_fail_closed_reason": final_reason,
            },
        })

    def _audit_metadata(
        self,
        selection,
        *,
        evidence_hash: str,
        retry_path: tuple[dict[str, object], ...],
        policy_attempts: tuple[dict[str, object], ...],
    ) -> dict[str, object]:
        return {
            "provider": "deepseek",
            "model_policy_version": self.model_policy.version,
            "runtime_audit_version": DECISION_AI_RUNTIME_AUDIT_VERSION,
            "model_tier": selection.tier,
            "selected_model": selection.model,
            "thinking": selection.thinking,
            "max_tokens": selection.max_tokens,
            "escalation_reasons": list(selection.escalation_reasons),
            "evidence_hash": evidence_hash,
            "assessment_schema_version": "ai-research-assessment-v1",
            "retry_fallback_path": list(retry_path),
            "policy_attempts": list(policy_attempts),
        }

    @staticmethod
    def _validate_references(assessment, evidence, candidates) -> None:
        # Reject invented citations and invented actions before persisting model
        # output. This keeps every visible AI claim traceable to the snapshot.
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
        """Accept a unique evidence title only when it maps unambiguously to supplied data."""
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


def _provider_success_audit(response) -> dict[str, object]:
    content_present, content_length, content_hash = _text_fingerprint(response.content)
    return {
        "provider_attempt_count": response.attempt_count,
        "provider_retry_codes": list(response.retry_codes),
        "response_model": response.model,
        "finish_reason": response.finish_reason,
        "content_present": content_present,
        "content_length": content_length,
        "content_hash": content_hash,
        "reasoning_present": response.reasoning_present,
        "reasoning_length": response.reasoning_length,
        "reasoning_hash": response.reasoning_hash,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "latency_ms": response.latency_ms,
    }


def _provider_error_audit(error: LlmClientError) -> dict[str, object]:
    return {
        "provider_attempt_count": error.attempt_count,
        "provider_retry_codes": list(error.retry_codes),
        "provider_error_code": error.code,
        "status_code": error.status_code,
        "finish_reason": error.finish_reason,
        "content_present": error.content_present,
        "content_length": error.content_length,
        "content_hash": error.content_hash,
        "reasoning_present": error.reasoning_present,
        "reasoning_length": error.reasoning_length,
        "reasoning_hash": error.reasoning_hash,
        "prompt_tokens": error.usage.prompt_tokens,
        "completion_tokens": error.usage.completion_tokens,
        "total_tokens": error.usage.total_tokens,
    }


def _validation_failure_audit(error: Exception, stage: str) -> dict[str, object]:
    paths: list[str] = []
    if isinstance(error, ValidationError):
        for item in error.errors():
            location = item.get("loc") or ()
            path = ".".join(str(part) for part in location)
            if path:
                paths.append(path)
    elif stage == "schema":
        paths.append("json_object")
    elif "evidence" in str(error).lower():
        paths.append("evidence_references")
    elif "action" in str(error).lower():
        paths.append("preferred_action")
    else:
        paths.append("semantic_invariants")
    return {
        "validation_result": "failed",
        "validation_error_class": type(error).__name__,
        "validation_error_paths": list(dict.fromkeys(paths)),
    }


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
        return min(max(int(os.getenv("DECISION_AI_MAX_TOKENS", "1200")), 700), 4800)
    except ValueError:
        logger.warning("DECISION_AI_MAX_TOKENS is invalid; using 1200")
        return 1200


def _hash_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _text_fingerprint(value: object) -> tuple[bool, int, str | None]:
    if not isinstance(value, str) or not value:
        return False, 0, None
    return True, len(value), hashlib.sha256(value.encode("utf-8")).hexdigest()
