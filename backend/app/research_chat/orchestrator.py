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
from .mcp_service import ThirdHandMcpService
from .tool_registry import definitions
from .models import ResearchModelOutput
from .guard import validate_output

logger = logging.getLogger(__name__)


def _flag(name: str) -> bool:
    return os.getenv(name, "false").lower() in {"1", "true", "yes", "on"}


def _positive_int_env(name: str, default: int) -> int:
    """Read a bounded loop limit without allowing an invalid value to disable it."""
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("Invalid %s; using default %s", name, default)
        return default


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
        self.tools = ThirdHandMcpService(store)

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
        tool_context_messages: list[dict[str, object]] = []
        try:
            logger.info("Research turn started turn_id=%s session_id=%s symbol=%s model=%s", turn.id, session.id, symbol or session.primary_symbol, self.stream_client.settings.reasoning_model)
            if not self.repo.history(session.id, limit=1):
                self.repo.update_session_title(session.id, user_message.strip()[:80])
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

            # Both the workbench and research chat now point to this exact
            # persisted report. The chat only explains it; it never creates a
            # second, potentially conflicting action recommendation.
            report = await asyncio.to_thread(self.decision_orchestrator.generate, context)
            self.store.save_decision_report(report.model_dump(mode="json"))
            decision_id = report.decision_id
            yield emit(ResearchSseEventType.decision, {"decision_report": report.model_dump(mode="json")})
            messages = build_messages(context, self.repo.history(session.id), user_message, report)
            self.repo.update_turn(turn.id, status=ResearchTurnStatus.streaming.value)
            yield emit(ResearchSseEventType.phase, {"phase": "streaming", "label": "正在进行研究分析"})
            tool_calls_used = 0
            tool_rounds_used = 0
            # A complete holding research commonly needs quote, position, daily
            # history, risk and business evidence.  Six calls cuts that normal
            # workflow off mid-answer, especially when the model groups calls
            # across multiple rounds.
            max_tool_calls = _positive_int_env("RESEARCH_CHAT_MAX_TOOL_CALLS", 12)
            max_tool_rounds = _positive_int_env("RESEARCH_CHAT_MAX_TOOL_ROUNDS", 4)
            tool_calling_active = _flag("RESEARCH_CHAT_TOOL_CALLING_ENABLED")
            tool_result_cache: dict[str, object] = {}
            while True:
                calls: dict[int, dict[str, object]] = {}
                round_truncated = False
                round_answer: list[str] = []
                round_reasoning: list[str] = []
                async for chunk in self.stream_client.stream_chat(
                    messages,
                    tools=definitions() if tool_calling_active else None,
                ):
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
                        reasoning_part = str(delta["reasoning_content"])
                        reasoning.append(reasoning_part)
                        round_reasoning.append(reasoning_part)
                        if _flag("RESEARCH_CHAT_REASONING_VISIBLE"):
                            yield emit(ResearchSseEventType.reasoning_delta, {"delta": reasoning_part})
                    if delta.get("content"):
                        answer_part = str(delta["content"])
                        answer.append(answer_part)
                        round_answer.append(answer_part)
                        yield emit(ResearchSseEventType.answer_delta, {"delta": answer_part})
                    for part in delta.get("tool_calls") or []:
                        index = int(part.get("index", 0))
                        call = calls.setdefault(index, {"id": str(part.get("id") or ""), "type": "function", "function": {"name": "", "arguments": ""}})
                        function = part.get("function") or {}
                        call["function"]["name"] += str(function.get("name") or "")
                        call["function"]["arguments"] += str(function.get("arguments") or "")
                if not calls:
                    completion_truncated = round_truncated
                    break
                if any(
                    not str(call.get("id") or "")
                    or not str((call.get("function") or {}).get("name") or "")
                    for call in calls.values()
                ):
                    raise LlmClientError(
                        "DeepSeek returned an incomplete tool call.",
                        code="invalid_response",
                        retryable=True,
                    )
                # DeepSeek requires the exact assistant tool_calls message followed by
                # one tool message per call.  Do not replay prior rounds' content here.
                assistant_tool_message = {
                    "role": "assistant",
                    "content": "".join(round_answer) or None,
                    "reasoning_content": "".join(round_reasoning) or None,
                    "tool_calls": list(calls.values()),
                }
                messages.append(assistant_tool_message)
                tool_context_messages.append(assistant_tool_message)
                tool_calls_used += len(calls)
                tool_rounds_used += 1
                limit_reached = (
                    tool_calls_used > max_tool_calls
                    or tool_rounds_used > max_tool_rounds
                )
                for call in calls.values():
                    function = call["function"]
                    tool_call_id = str(call.get("id") or "")
                    name = str(function["name"])
                    logger.info("Research tool started turn_id=%s tool=%s", turn.id, name)
                    yield emit(ResearchSseEventType.tool_started, {"tool_name": name})
                    try:
                        arguments = json.loads(function["arguments"] or "{}")
                        if not isinstance(arguments, dict):
                            raise ValueError("tool_arguments_must_be_object")
                        if limit_reached:
                            result = {
                                "error": "tool_budget_reached",
                                "message": "Tool research budget is complete. Use the context and prior tool results to write the final answer; do not request more tools.",
                            }
                            self.repo.save_tool_call(turn.id, name, arguments, "skipped", result)
                        else:
                            cache_key = f"{name}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True)}"
                            if cache_key in tool_result_cache:
                                result = tool_result_cache[cache_key]
                                self.repo.save_tool_call(turn.id, name, arguments, "completed", result)
                                logger.info("Research tool reused cached result turn_id=%s tool=%s", turn.id, name)
                            else:
                                result = self.tools.call_tool(name, arguments, context)
                                tool_result_cache[cache_key] = result
                                self.repo.save_tool_call(turn.id, name, arguments, "completed", result)
                                logger.info("Research tool completed turn_id=%s tool=%s", turn.id, name)
                    except Exception as error:
                        self.repo.save_tool_call(turn.id, name, {}, "failed", error="tool_invalid_arguments")
                        logger.exception("Research tool failed turn_id=%s tool=%s", turn.id, name)
                        yield emit(ResearchSseEventType.tool_failed, {"tool_name": name, "error_code": "tool_invalid_arguments"})
                        # A tool result must still be returned against the model-issued
                        # ID, allowing the model to repair its call on the next round.
                        result = {"error": "tool_invalid_arguments", "message": str(error)[:240]}
                    questions = _clarification_questions(result)
                    if questions and _flag("RESEARCH_CHAT_CLARIFICATION_ENABLED"):
                        item = self.repo.create_clarification(turn.id, "模型需要补充", questions)
                        self.repo.update_turn(turn.id, status=ResearchTurnStatus.waiting_user.value)
                        yield emit(ResearchSseEventType.clarification_required, item)
                        yield emit(ResearchSseEventType.done, {"status": "waiting_user", "turn_id": turn.id})
                        return
                    yield emit(ResearchSseEventType.tool_completed, {"tool_name": name, "result": result})
                    tool_message = {"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(result, ensure_ascii=False, default=str)}
                    messages.append(tool_message)
                    tool_context_messages.append(tool_message)
                if limit_reached:
                    # Do not crash the entire SSE turn.  Replying to every
                    # model-issued tool call keeps the DeepSeek transcript valid;
                    # removing tools on the next pass forces a bounded final answer.
                    tool_calling_active = False
                    logger.warning(
                        "Research tool budget reached turn_id=%s calls=%s/%s rounds=%s/%s",
                        turn.id,
                        tool_calls_used,
                        max_tool_calls,
                        tool_rounds_used,
                        max_tool_rounds,
                    )
                    yield emit(
                        ResearchSseEventType.warning,
                        {
                            "code": "tool_budget_reached",
                            "message": "研究已取得可用资料，正在基于现有资料整理结论。",
                        },
                    )

            final_answer = "".join(answer).strip()
            self.repo.add_message(session.id, turn.id, "user", "user_text", user_message)
            for message in tool_context_messages:
                content_type = "assistant_tool_context" if message["role"] == "assistant" else "tool_result_context"
                self.repo.add_message(session.id, turn.id, str(message["role"]), content_type, json.dumps(message, ensure_ascii=False, default=str))
            self.repo.add_message(session.id, turn.id, "assistant", "assistant_answer", final_answer)
            answer_persisted = True
            # ``decision_id`` belongs to the canonical report emitted before
            # streaming. Do not derive another report from chat prose.
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
