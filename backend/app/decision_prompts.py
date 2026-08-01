"""Prompts for bounded evidence research; never ask for quantities or trade execution."""
from __future__ import annotations

import json


def decision_research_messages(context, evidence, candidates) -> list[dict[str, str]]:
    allowed_actions = [candidate.action for candidate in candidates]
    payload = {
        "symbol": context.symbol,
        "name": context.name,
        "decision_horizon": context.decision_horizon,
        "data_quality": context.data_quality.model_dump(mode="json"),
        "position": context.position.model_dump(mode="json") if context.position else None,
        "quote": context.quote.model_dump(mode="json") if context.quote else None,
        "technical": context.technical.model_dump(mode="json") if context.technical else None,
        "risk": context.risk.model_dump(mode="json") if context.risk else None,
        "market_regime": context.market_regime.model_dump(mode="json") if context.market_regime else None,
        "relative_strength": context.relative_strength.model_dump(mode="json") if context.relative_strength else None,
        "trade_plan": context.trade_plan.model_dump(mode="json") if context.trade_plan else None,
        "events": [item.model_dump(mode="json") for item in context.events],
        "allowed_actions": allowed_actions,
        "evidence": [{"evidence_id": item.evidence_id, "direction": item.direction, "strength": item.strength, "title": item.title, "description": item.description, "value": item.value, "threshold": item.threshold, "fresh": item.fresh} for item in evidence],
    }
    return [
        {"role": "system", "content": "You are a constrained investment research assistant. Return JSON only. Compare the position, market regime, trade plan and event evidence for this specific symbol; identify concrete conflicts using supplied values, rather than generic risk language. Do not give prices, quantities, execution instructions, or actions outside allowed_actions. Cite only supplied evidence_id values. Summarize evidence conflicts and uncertainty without hidden chain-of-thought."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
