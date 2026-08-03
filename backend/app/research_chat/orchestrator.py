"""Bounded server-side research flow.  It emits only Third-Hand SSE events."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from app.llm_client import LlmClientError
from app.llm_client import DeepSeekClient
from app.decision_models import DecisionReport
from app.time_utils import beijing_now

from .clarification import needs_clarification
from .metrics import inc
from .models import ResearchSseEvent, ResearchSseEventType, ResearchTurnStatus
from .prompt_builder import build_messages
from .sse import encode_event
from .stream_client import DeepSeekStreamClient
from .tool_executor import ToolExecutor
from .tool_registry import definitions
from .models import ResearchModelOutput
from .guard import validate_output

logger = logging.getLogger(__name__)


def _flag(name: str) -> bool:
    return os.getenv(name, "false").lower() in {"1", "true", "yes", "on"}


def _clarification_questions(result: object) -> list[str] | None:
    """Only the dedicated input tool may turn a tool result into a clarification.

    Most read-only tools correctly return lists (holdings, events, reports) or
    scalars.  They are valid tool payloads and must not be treated as mappings.
    """
    if not isinstance(result, dict) or result.get("clarification") is not True:
        return None
    questions = result.get("questions")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 3:
        raise ValueError("tool_invalid_clarification_payload")
    return [str(question)[:240] for question in questions]


class ResearchChatOrchestrator:
    def __init__(self, repo, context_builder, store, decision_orchestrator) -> None:
        self.repo = repo
        self.context_builder = context_builder
        self.store = store
        self.decision_orchestrator = decision_orchestrator
        self.stream_client = DeepSeekStreamClient()
        self.json_client = DeepSeekClient()
        self.tools = ToolExecutor(store)

    async def stream(self, session, turn, user_message: str, symbol: str | None):
        event_id = 0

        def emit(kind, data) -> str:
            nonlocal event_id
            event_id += 1
            return encode_event(event_id, ResearchSseEvent(event=kind, data=data))

        started = time.monotonic()
        answer: list[str] = []
        reasoning: list[str] = []
        usage: dict[str, object] = {}
        completion_truncated = False
        answer_persisted = False
        final_answer = ""
        try:
            logger.info("Research turn started turn_id=%s session_id=%s symbol=%s model=%s", turn.id, session.id, symbol or session.primary_symbol, self.stream_client.settings.reasoning_model)
            inc("research_chat_turn_total")
            self.repo.update_turn(turn.id, status=ResearchTurnStatus.building_context.value, started_at=beijing_now().isoformat())
            yield emit(ResearchSseEventType.session, {"session_id": session.id, "turn_id": turn.id})
            yield emit(ResearchSseEventType.phase, {"phase": "building_context", "label": "正在加载统一决策上下文"})
            context = self.context_builder.build(symbol or session.primary_symbol or "")
            self.repo.update_turn(turn.id, context_id=context.context_id, context_hash=context.input_hash)
            yield emit(ResearchSseEventType.evidence, {"context_id": context.context_id, "data_quality": context.data_quality.status, "event_ids": [item.event_id for item in context.events]})

            questions = needs_clarification(context, user_message) if _flag("RESEARCH_CHAT_CLARIFICATION_ENABLED") else []
            if questions:
                item = self.repo.create_clarification(turn.id, "关键决策数据不足", questions)
                self.repo.update_turn(turn.id, status=ResearchTurnStatus.waiting_user.value)
                yield emit(ResearchSseEventType.clarification_required, item)
                yield emit(ResearchSseEventType.done, {"status": "waiting_user", "turn_id": turn.id})
                return
            if not self.stream_client.enabled:
                raise LlmClientError("未配置 DeepSeek 研究模型。", code="model_not_configured", retryable=False)

            messages = build_messages(context, self.repo.history(session.id), user_message)
            self.repo.update_turn(turn.id, status=ResearchTurnStatus.streaming.value)
            yield emit(ResearchSseEventType.phase, {"phase": "streaming", "label": "正在进行研究分析"})
            tool_rounds = 0
            while True:
                calls: dict[int, dict[str, object]] = {}
                round_truncated = False
                async for chunk in self.stream_client.stream_chat(messages, tools=definitions() if _flag("RESEARCH_CHAT_TOOL_CALLING_ENABLED") else None):
                    current_turn = self.repo.turn(turn.id)
                    if current_turn and current_turn.status == ResearchTurnStatus.cancelled:
                        yield emit(ResearchSseEventType.done, {"status": "cancelled", "turn_id": turn.id})
                        return
                    usage = chunk.get("usage") or usage
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    if choices[0].get("finish_reason") == "length":
                        round_truncated = True
                    delta = choices[0].get("delta") or {}
                    if delta.get("reasoning_content"):
                        reasoning.append(str(delta["reasoning_content"]))
                        if _flag("RESEARCH_CHAT_REASONING_VISIBLE"):
                            yield emit(ResearchSseEventType.reasoning_delta, {"delta": delta["reasoning_content"]})
                    if delta.get("content"):
                        answer.append(str(delta["content"]))
                        yield emit(ResearchSseEventType.answer_delta, {"delta": delta["content"]})
                    for part in delta.get("tool_calls") or []:
                        index = int(part.get("index", 0))
                        call = calls.setdefault(index, {"id": str(part.get("id") or ""), "type": "function", "function": {"name": "", "arguments": ""}})
                        function = part.get("function") or {}
                        call["function"]["name"] += str(function.get("name") or "")
                        call["function"]["arguments"] += str(function.get("arguments") or "")
                if not calls:
                    completion_truncated = round_truncated
                    break
                tool_rounds += 1
                if tool_rounds > 4:
                    raise RuntimeError("tool_loop_limit")
                messages.append({"role": "assistant", "content": "".join(answer) or None, "reasoning_content": "".join(reasoning), "tool_calls": list(calls.values())})
                for call in calls.values():
                    function = call["function"]
                    name = function["name"]
                    logger.info("Research tool started turn_id=%s tool=%s", turn.id, name)
                    yield emit(ResearchSseEventType.tool_started, {"tool_name": name})
                    try:
                        arguments = json.loads(function["arguments"] or "{}")
                        result = self.tools.execute(name, arguments, context)
                        self.repo.save_tool_call(turn.id, name, arguments, "completed", result)
                        logger.info("Research tool completed turn_id=%s tool=%s", turn.id, name)
                    except Exception:
                        self.repo.save_tool_call(turn.id, name, {}, "failed", error="tool_invalid_arguments")
                        logger.exception("Research tool failed turn_id=%s tool=%s", turn.id, name)
                        yield emit(ResearchSseEventType.tool_failed, {"tool_name": name, "error_code": "tool_invalid_arguments"})
                        raise
                    questions = _clarification_questions(result)
                    if questions and _flag("RESEARCH_CHAT_CLARIFICATION_ENABLED"):
                        item = self.repo.create_clarification(turn.id, "模型需要补充", questions)
                        self.repo.update_turn(turn.id, status=ResearchTurnStatus.waiting_user.value)
                        yield emit(ResearchSseEventType.clarification_required, item)
                        yield emit(ResearchSseEventType.done, {"status": "waiting_user", "turn_id": turn.id})
                        return
                    yield emit(ResearchSseEventType.tool_completed, {"tool_name": name, "result": result})
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False, default=str)})

            final_answer = "".join(answer).strip()
            self.repo.add_message(session.id, turn.id, "user", "user_text", user_message)
            self.repo.add_message(session.id, turn.id, "assistant", "assistant_answer", final_answer)
            answer_persisted = True
            decision_id = None
            if _flag("RESEARCH_CHAT_DECISION_OUTPUT_ENABLED"):
                evidence = self.decision_orchestrator.evidence_engine.build(context)
                output = await asyncio.to_thread(self._decision_output, context, final_answer, [item.evidence_id for item in evidence])
                candidates = self.decision_orchestrator.policy_engine.evaluate(context, evidence)
                assessment = validate_output(output, {item.evidence_id for item in evidence}, candidates)
                if assessment is None:
                    yield emit(ResearchSseEventType.warning, {"code": "decision_guard_blocked", "message": "研究结论未通过证据与动作边界校验，未生成决策报告。"})
                    raise LlmClientError("研究结论未通过决策保护。", code="decision_guard_blocked", retryable=False)
                sizing = self.decision_orchestrator.sizing_engine.size(context, assessment.preferred_action)
                report = DecisionReport(
                    decision_id=__import__("uuid").uuid4().hex,
                    context_id=context.context_id,
                    symbol=context.symbol,
                    generated_at=beijing_now(),
                    status="BLOCKED" if context.data_quality.status == "blocked" else "DEGRADED" if context.data_quality.status == "degraded" else "READY",
                    action=assessment.preferred_action,
                    summary=output.answer_summary,
                    evidence=evidence,
                    action_candidates=candidates,
                    ai_assessment=assessment,
                    ai_status="succeeded",
                    sizing=sizing,
                    policy_version=self.decision_orchestrator.policy_engine.version,
                    prompt_version="research-chat-decision-v1",
                    model=self.json_client.settings.model,
                    input_hash=context.input_hash,
                )
                self.store.save_decision_report(report.model_dump(mode="json"))
                decision_id = report.decision_id
                yield emit(ResearchSseEventType.decision, {"decision_report": report.model_dump(mode="json")})
            self.repo.update_turn(turn.id, status=ResearchTurnStatus.completed.value, answer_text=final_answer, decision_report_id=decision_id, prompt_tokens=int(usage.get("prompt_tokens") or 0), completion_tokens=int(usage.get("completion_tokens") or 0), latency_ms=int((time.monotonic() - started) * 1000), completed_at=beijing_now().isoformat())
            inc("research_chat_turn_completed")
            logger.info("Research turn completed turn_id=%s model=%s latency_ms=%s prompt_tokens=%s completion_tokens=%s", turn.id, self.stream_client.settings.reasoning_model, int((time.monotonic() - started) * 1000), int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0))
            yield emit(ResearchSseEventType.usage, {"prompt_tokens": int(usage.get("prompt_tokens") or 0), "completion_tokens": int(usage.get("completion_tokens") or 0)})
            yield emit(ResearchSseEventType.done, {"status": "truncated" if completion_truncated else "completed", "turn_id": turn.id, "automatic_execution": False, "can_continue": completion_truncated})
        except asyncio.CancelledError:
            self.repo.update_turn(turn.id, status=ResearchTurnStatus.cancelled.value, completed_at=beijing_now().isoformat())
            inc("research_chat_cancel_total")
            raise
        except LlmClientError as error:
            if answer_persisted:
                logger.warning("Research post-answer artifact skipped turn_id=%s code=%s", turn.id, error.code)
                self.repo.update_turn(turn.id, status=ResearchTurnStatus.completed.value, answer_text=final_answer, prompt_tokens=int(usage.get("prompt_tokens") or 0), completion_tokens=int(usage.get("completion_tokens") or 0), latency_ms=int((time.monotonic() - started) * 1000), completed_at=beijing_now().isoformat())
                yield emit(ResearchSseEventType.warning, {"code": "decision_artifact_unavailable", "message": "研究回答已完成；附加决策报告暂未生成。"})
                yield emit(ResearchSseEventType.usage, {"prompt_tokens": int(usage.get("prompt_tokens") or 0), "completion_tokens": int(usage.get("completion_tokens") or 0)})
                yield emit(ResearchSseEventType.done, {"status": "truncated" if completion_truncated else "completed", "turn_id": turn.id, "automatic_execution": False, "can_continue": completion_truncated})
                return
            inc("research_chat_upstream_errors_total")
            self.repo.update_turn(turn.id, status=ResearchTurnStatus.failed.value, error_code=error.code, error_message=str(error), completed_at=beijing_now().isoformat())
            logger.warning("Research turn failed turn_id=%s model=%s code=%s status=%s", turn.id, self.stream_client.settings.reasoning_model, error.code, error.status_code)
            yield emit(ResearchSseEventType.error, {"code": error.code, "message": str(error)})
            yield emit(ResearchSseEventType.done, {"status": "failed", "turn_id": turn.id})
        except Exception:
            if answer_persisted:
                logger.exception("Research post-answer artifact skipped turn_id=%s", turn.id)
                self.repo.update_turn(turn.id, status=ResearchTurnStatus.completed.value, answer_text=final_answer, prompt_tokens=int(usage.get("prompt_tokens") or 0), completion_tokens=int(usage.get("completion_tokens") or 0), latency_ms=int((time.monotonic() - started) * 1000), completed_at=beijing_now().isoformat())
                yield emit(ResearchSseEventType.warning, {"code": "decision_artifact_unavailable", "message": "研究回答已完成；附加决策报告暂未生成。"})
                yield emit(ResearchSseEventType.usage, {"prompt_tokens": int(usage.get("prompt_tokens") or 0), "completion_tokens": int(usage.get("completion_tokens") or 0)})
                yield emit(ResearchSseEventType.done, {"status": "truncated" if completion_truncated else "completed", "turn_id": turn.id, "automatic_execution": False, "can_continue": completion_truncated})
                return
            inc("research_chat_upstream_errors_total")
            self.repo.update_turn(turn.id, status=ResearchTurnStatus.failed.value, error_code="upstream_invalid_response", error_message="研究流处理失败", completed_at=beijing_now().isoformat())
            logger.exception("Research turn crashed turn_id=%s model=%s", turn.id, self.stream_client.settings.reasoning_model)
            yield emit(ResearchSseEventType.error, {"code": "upstream_invalid_response", "message": "研究流处理失败"})
            yield emit(ResearchSseEventType.done, {"status": "failed", "turn_id": turn.id})

    def _decision_output(self, context, answer: str, evidence_ids: list[str]) -> ResearchModelOutput:
        """A separate fast JSON pass. Numbers in prose are never used as sizing."""
        prompt = {
            "symbol": context.symbol,
            "answer": answer,
            "allowed_actions": ["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"],
            "evidence_ids": evidence_ids,
        }
        response = self.json_client.chat_json([
            {"role": "system", "content": "Return JSON only matching ResearchModelOutput. Cite only supplied evidence IDs. Do not include quantity, price, execution, or automatic trading."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ], max_tokens=900, thinking=False)
        return ResearchModelOutput.model_validate_json(response.content)
