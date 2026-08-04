"""Prompts for bounded evidence research; never ask for quantities or trade execution."""
from __future__ import annotations

import json


def _as_json(value):
    if value is None:
        return None
    dump = getattr(value, "model_dump", None)
    return dump(mode="json") if callable(dump) else {"status": getattr(value, "status", "unknown")}


def decision_research_messages(context, evidence, candidates) -> list[dict[str, str]]:
    allowed_actions = [candidate.action for candidate in candidates]
    payload = {
        "symbol": context.symbol,
        # Older context fixtures and persisted pre-unification snapshots do not
        # carry a display name.  It is descriptive only and must not block the
        # constrained policy path.
        "name": getattr(context, "name", ""),
        "decision_horizon": getattr(context, "decision_horizon", "swing"),
        "data_quality": _as_json(getattr(context, "data_quality", None)),
        "position": _as_json(getattr(context, "position", None)),
        "quote": _as_json(getattr(context, "quote", None)),
        "technical": _as_json(getattr(context, "technical", None)),
        "risk": _as_json(getattr(context, "risk", None)),
        "market_regime": _as_json(getattr(context, "market_regime", None)),
        "relative_strength": _as_json(getattr(context, "relative_strength", None)),
        "trade_plan": _as_json(getattr(context, "trade_plan", None)),
        "events": [item.model_dump(mode="json") for item in getattr(context, "events", ())],
        "allowed_actions": allowed_actions,
        "evidence": [{"evidence_id": item.evidence_id, "direction": item.direction, "strength": item.strength, "title": item.title, "description": item.description, "value": item.value, "threshold": item.threshold, "fresh": item.fresh} for item in evidence],
    }
    return [
        {"role": "system", "content": "You are a constrained investment research assistant. Return one valid JSON object only: no Markdown, no prose before or after it. Use every required key exactly once: thesis_status, preferred_action, supporting_evidence_ids, opposing_evidence_ids, missing_evidence, reasoning_steps, rule_suggestions, uncertainty, summary. Evidence references must be copied character-for-character from the supplied evidence_id list; never use titles, descriptions, invented IDs, or URLs. rule_suggestions is [] unless the supplied risk/position evidence gives a concrete reason to improve a personal rule. Each suggestion is non-binding and must contain scope, symbol (only for symbol scope), any proposed max_position_percent/loss_review_percent/volatility_review_percent, rationale, and risk_note. Never propose prices, quantities, trade execution, or a change outside supplied evidence. An enabled trade_plan is a hard constraint and cannot be overridden. Empty evidence lists are allowed. Be concise: use at most 4 reasoning steps and plain Chinese summaries. A plan marked is_draft is not enabled: continue with conservative qualitative analysis and explain that it is editable later; never treat it as permission to open or add. Summarize evidence conflicts and uncertainty without hidden chain-of-thought."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
