"""Prompts limit the chat to explanation and evidence, never execution."""
from __future__ import annotations
import json
PROMPT_VERSION="research-chat-v2-unified-report"
def build_messages(context,history,user_message,report=None):
 summary={"context_id":context.context_id,"symbol":context.symbol,"name":context.name,"data_quality":context.data_quality.model_dump(mode="json"),"position":context.position.model_dump(mode="json") if context.position else None,"quote":context.quote.model_dump(mode="json") if context.quote else None,"technical":context.technical.model_dump(mode="json") if context.technical else None,"risk":context.risk.model_dump(mode="json") if context.risk else None,"trade_plan":context.trade_plan.model_dump(mode="json") if context.trade_plan else None,"events":[item.model_dump(mode="json") for item in context.events]}
 canonical = report.model_dump(mode="json") if report else None
 messages=[{"role":"system","content":"You are a read-only investment research assistant. The Canonical Analysis Report below is the ONLY source of recommendation action. Do not create, change, or imply a different buy/sell/hold/watch action, quantity, price, or execution instruction. Explain that report, answer questions using supplied facts, and state when the report needs refresh after new information. Cite evidence IDs when known. An enabled trade plan is binding; a draft plan is editable context only and must never enable an action. Use tools only when they materially add information not already present in Shared DecisionContext. Never repeat a tool call with the same arguments. Formal announcements take precedence over news. State missing data. Format visible answers in concise Markdown using headings and bullets. Do not use raw HTML, tables, or hidden reasoning."},{"role":"system","content":"Canonical Analysis Report:\n"+json.dumps(canonical,ensure_ascii=False,default=str)},{"role":"system","content":"Shared DecisionContext:\n"+json.dumps(summary,ensure_ascii=False,default=str)}]
 for item in history[-24:]:
  try:
   message=json.loads(item["content"]) if item["role"] in {"assistant","tool"} else {"role":item["role"],"content":item["content"]}
  except (TypeError,json.JSONDecodeError):
   continue
  if isinstance(message,dict) and message.get("role")==item["role"]:
   messages.append(message)
 messages.append({"role":"user","content":user_message})
 return messages
