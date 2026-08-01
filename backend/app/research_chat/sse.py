"""SSE encoding that never proxies an upstream provider's wire format."""
from __future__ import annotations

import json
from collections.abc import Iterator

from .models import ResearchSseEvent, ResearchSseEventType

SSE_CONTENT_TYPE = "text/event-stream"
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def encode_event(event_id: int, event: ResearchSseEvent) -> str:
    """Encode exactly one event with single-line JSON data."""
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.event.value}\nid: {event_id}\ndata: {payload}\n\n"


def fake_research_stream(session_id: str, turn_id: str, message: str, is_cancelled) -> Iterator[str]:
    """Local deterministic stream used only during protocol phase one."""
    events = [
        (ResearchSseEventType.session, {"session_id": session_id, "turn_id": turn_id}),
        (ResearchSseEventType.phase, {"phase": "building_context", "label": "正在准备研究上下文"}),
        (ResearchSseEventType.heartbeat, {"status": "alive"}),
        (ResearchSseEventType.answer_delta, {"delta": "这是本地假流响应："}),
        (ResearchSseEventType.answer_delta, {"delta": f"已收到你的问题“{message}”。"}),
        (ResearchSseEventType.done, {"status": "completed", "turn_id": turn_id}),
    ]
    for event_id, (event_type, data) in enumerate(events, start=1):
        if is_cancelled():
            yield encode_event(event_id, ResearchSseEvent(event=ResearchSseEventType.done, data={"status": "cancelled", "turn_id": turn_id}))
            return
        yield encode_event(event_id, ResearchSseEvent(event=event_type, data=data))
