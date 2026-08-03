import json

from app.decision_ai import DecisionAiService
from app.decision_guard import DecisionGuard
from app.decision_models import ActionCandidate, AiResearchAssessment
from app.llm_client import LlmClientError, LlmResponse, LlmUsage


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


def test_ai_service_rejects_unknown_evidence_and_preserves_rule_fallback():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["unknown"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "reduce"}
    store = Store()
    result = DecisionAiService(store, Client(json.dumps(payload))).assess(Context(), _evidence(), (_candidate(),))

    assert result.assessment is None
    assert result.status == "failed"
    assert result.error_code == "invalid_ai_output"
    assert store.runs[-1]["status"] == "failed"


def test_ai_service_accepts_a_fenced_json_response_and_canonicalizes_a_unique_title():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["cap"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "需要留意仓位上限。"}
    store = Store()
    result = DecisionAiService(store, Client(f"```json\n{json.dumps(payload)}\n``` ")).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert result.assessment.supporting_evidence_ids == ("position.above_max",)


def test_ai_service_does_not_repeat_a_truncated_request():
    class TruncatingClient(Client):
        def chat_json(self, *_args, **_kwargs):
            self.calls += 1
            raise LlmClientError("truncated", code="output_truncated", retryable=False)

    store = Store()
    client = TruncatingClient("")
    result = DecisionAiService(store, client).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "failed"
    assert result.error_code == "output_truncated"
    assert client.calls == 1


def test_guard_rejects_ai_action_outside_policy_candidates():
    assessment = AiResearchAssessment(thesis_status="unknown", preferred_action="ADD", uncertainty="high", summary="add")

    assert DecisionGuard().guard((_candidate("REDUCE"),), assessment) is None
