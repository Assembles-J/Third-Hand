import json
from pathlib import Path

from app.decision_ai import DecisionAiService
from app.decision_guard import DecisionGuard
from app.decision_models import ActionCandidate, AiResearchAssessment
from app.llm_client import LlmClientError, LlmResponse, LlmUsage
from app.storage import PortfolioStore


class Store:
    def __init__(self): self.runs = []
    def save_decision_ai_run(self, item): self.runs.append(item)


class Client:
    enabled = True
    def __init__(self, content): self.content = content; self.calls = 0
    def chat_json(self, *_args, **_kwargs):
        self.calls += 1
        return LlmResponse(content=self.content, model="test", latency_ms=1, usage=LlmUsage())


class Context:
    context_id = "context"; input_hash = "hash"; symbol = "600519"
    class data_quality: status = "ready"


def _candidate(action="REDUCE"):
    return ActionCandidate(action=action, priority=80, policy_score=.8)


def _evidence():
    from app.decision_models import EvidenceItem
    return (EvidenceItem(evidence_id="position.above_max", category="position", direction="negative", strength=.7, title="cap", description="cap", source="test", fresh=True),)


def test_ai_service_accepts_only_known_evidence_and_policy_candidate():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["position.above_max"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "reduce"}
    store = Store()
    result = DecisionAiService(store, Client(json.dumps(payload))).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert result.assessment.preferred_action == "REDUCE"
    assert store.runs[0]["status"] == "succeeded"
    metadata = store.runs[0]["metadata"]
    assert metadata["model_tier"] == "FLASH_DEFAULT"
    assert len(metadata["prompt_hash"]) == 64
    assert len(metadata["evidence_hash"]) == 64
    assert metadata["validation"] == "schema_and_semantic_passed"
    assert metadata["provider_attempt_count"] == 1
    assert metadata["provider_retry_codes"] == []


def test_ai_service_rejects_unknown_evidence_and_preserves_rule_fallback():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["unknown"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "reduce"}
    store = Store()
    result = DecisionAiService(store, Client(json.dumps(payload))).assess(Context(), _evidence(), (_candidate(),))

    assert result.assessment is None
    assert result.status == "failed"
    assert result.error_code == "invalid_ai_output"
    assert store.runs[-1]["status"] == "failed"
    assert store.runs[-1]["metadata"]["retry_fallback_path"][0]["reason"] == "schema_or_semantic_validation_failed"


def test_ai_service_accepts_a_fenced_json_response_and_canonicalizes_a_unique_title():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["cap"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "需要留意仓位上限。"}
    store = Store()
    result = DecisionAiService(store, Client(f"```json\n{json.dumps(payload)}\n``` ")).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert result.assessment.supporting_evidence_ids == ("position.above_max",)


def test_ai_service_recovers_a_truncated_thinking_request_with_larger_structured_pass():
    class TruncatingClient(Client):
        def chat_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise LlmClientError("truncated", code="output_truncated", retryable=False)
            return LlmResponse(
                content=json.dumps({
                    "thesis_status": "weakened", "preferred_action": "REDUCE",
                    "supporting_evidence_ids": [], "opposing_evidence_ids": [],
                    "missing_evidence": [], "reasoning_steps": [],
                    "uncertainty": "medium", "summary": "recovered",
                }),
                model="test", latency_ms=1, usage=LlmUsage(),
            )

    store = Store()
    client = TruncatingClient("")
    result = DecisionAiService(store, client).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert client.calls == 2
    metadata = store.runs[-1]["metadata"]
    assert metadata["model_tier"] == "PRO_STRUCTURED_RECOVERY"
    assert metadata["thinking"] is False
    assert metadata["max_tokens"] >= 2400
    assert metadata["retry_fallback_path"][0]["reason"] == "output_truncated"


def test_ai_service_promotes_flash_validation_failure_to_reasoning_model():
    valid = json.dumps({
        "thesis_status": "weakened", "preferred_action": "REDUCE",
        "supporting_evidence_ids": [], "opposing_evidence_ids": [],
        "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "recovered",
    })

    class RepairingClient(Client):
        def chat_json(self, *_args, **kwargs):
            self.calls += 1
            self.last_kwargs = kwargs
            return LlmResponse(
                content="not-json" if self.calls == 1 else valid,
                model="test", latency_ms=1, usage=LlmUsage(),
            )

    store = Store()
    client = RepairingClient("")
    result = DecisionAiService(store, client).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert client.calls == 2
    metadata = store.runs[-1]["metadata"]
    assert metadata["model_tier"] == "PRO_ESCALATION"
    assert metadata["thinking"] is True
    assert metadata["retry_fallback_path"][0]["from_tier"] == "FLASH_DEFAULT"
    assert metadata["retry_fallback_path"][0]["to_tier"] == "PRO_ESCALATION"


def test_guard_rejects_ai_action_outside_policy_candidates():
    assessment = AiResearchAssessment(thesis_status="unknown", preferred_action="ADD", uncertainty="high", summary="add")

    assert DecisionGuard().guard((_candidate("REDUCE"),), assessment) is None


def test_persisted_model_audit_is_readable_without_secrets(tmp_path: Path):
    store = PortfolioStore(tmp_path / "model-audit.db")
    store.save_decision_ai_run({
        "run_id": "run-1", "context_id": "context-1", "input_hash": "input-1",
        "status": "succeeded", "error_code": None, "payload": {},
        "metadata": {"prompt_hash": "a" * 64, "retry_fallback_path": []},
        "created_at": "2026-08-18T10:00:00+08:00",
    })

    audit = store.decision_ai_runs("context-1")

    assert audit[0]["metadata"]["prompt_hash"] == "a" * 64
    assert "api_key" not in audit[0]["metadata"]
