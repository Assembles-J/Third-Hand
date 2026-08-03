import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.research_chat.models import ResearchSseEvent, ResearchSseEventType
from app.research_chat.orchestrator import _clarification_questions
from app.research_chat.sse import encode_event


client = TestClient(app)


def test_sse_encoder_uses_single_line_json_and_protocol_version():
    encoded = encode_event(7, ResearchSseEvent(event=ResearchSseEventType.answer_delta, data={"delta": "一行\n内容"}))

    assert encoded.startswith("event: answer_delta\nid: 7\ndata: ")
    assert encoded.endswith("\n\n")
    data_line = encoded.splitlines()[2]
    assert "\n" not in data_line
    assert json.loads(data_line.removeprefix("data: ")) == {
        "protocol": "research-sse-v1",
        "event": "answer_delta",
        "data": {"delta": "一行\n内容"},
    }


def test_research_chat_is_inert_when_feature_flag_is_disabled(monkeypatch):
    monkeypatch.delenv("RESEARCH_CHAT_ENABLED", raising=False)

    response = client.post("/v1/research-chat/sessions", json={"title": "研究"})

    assert response.status_code == 404


def test_read_only_list_tool_result_is_not_mistaken_for_a_clarification():
    assert _clarification_questions([{"symbol": "600519"}]) is None
    assert _clarification_questions({"clarification": True, "questions": ["请确认持仓成本"]}) == ["请确认持仓成本"]


def test_research_stream_is_versioned_and_reports_missing_model_without_leaking_upstream(monkeypatch):
    monkeypatch.setenv("RESEARCH_CHAT_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_CHAT_SSE_ENABLED", "true")
    session = client.post("/v1/research-chat/sessions", json={"title": "小米研究", "primary_symbol": "01810"})
    assert session.status_code == 201

    response = client.post(
        f"/v1/research-chat/sessions/{session.json()['id']}/messages/stream",
        json={"message": "为什么需要复核？", "symbol": "01810", "client_request_id": str(uuid4())},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    blocks = [block for block in response.text.split("\n\n") if block]
    parsed = [json.loads(next(line[6:] for line in block.splitlines() if line.startswith("data: "))) for block in blocks]
    assert [item["event"] for item in parsed] == ["session", "phase", "evidence", "error", "done"]
    assert all(item["protocol"] == "research-sse-v1" for item in parsed)
    assert parsed[-2]["data"]["code"] == "model_not_configured"
    assert parsed[-1]["data"]["status"] == "failed"
