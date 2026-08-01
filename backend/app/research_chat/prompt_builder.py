"""Prompts limit the chat to explanation and evidence, never execution."""
from __future__ import annotations
import json
PROMPT_VERSION="research-chat-v1"
def build_messages(context,history,user_message):
 summary={"context_id":context.context_id,"symbol":context.symbol,"name":context.name,"data_quality":context.data_quality.model_dump(mode="json"),"position":context.position.model_dump(mode="json") if context.position else None,"quote":context.quote.model_dump(mode="json") if context.quote else None,"technical":context.technical.model_dump(mode="json") if context.technical else None,"risk":context.risk.model_dump(mode="json") if context.risk else None,"trade_plan":context.trade_plan.model_dump(mode="json") if context.trade_plan else None,"events":[item.model_dump(mode="json") for item in context.events]}
 messages=[{"role":"system","content":"You are a read-only investment research assistant. Explain only supplied facts; do not claim to trade, create orders, set quantities, or bypass the decision policy. Cite evidence IDs when known. State missing data. Your visible answer is concise; do not expose hidden reasoning."},{"role":"system","content":"Shared DecisionContext:\n"+json.dumps(summary,ensure_ascii=False,default=str)}]
 messages.extend({"role":item["role"],"content":item["content"]} for item in history[-12:])
 messages.append({"role":"user","content":user_message})
 return messages
