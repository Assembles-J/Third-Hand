"""Prompts for bounded evidence research; never ask for quantities or trade execution."""
from __future__ import annotations

import json


def decision_research_messages(context, evidence, candidates) -> list[dict[str, str]]:
    allowed_actions = [candidate.action for candidate in candidates]
    payload = {
        "symbol": context.symbol,
        "data_quality": context.data_quality.status,
        "allowed_actions": allowed_actions,
        "evidence": [{"evidence_id": item.evidence_id, "direction": item.direction, "title": item.title} for item in evidence],
    }
    return [
        {"role": "system", "content": "You are a constrained research assistant. Return JSON only. Do not give prices, quantities, execution instructions, or actions outside allowed_actions. Cite only supplied evidence_id values. Summarize evidence conflicts and uncertainty without hidden chain-of-thought."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
