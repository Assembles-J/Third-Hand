"""Explicit, read-only tool definitions exposed to the research model."""
from __future__ import annotations

ALLOWED_TOOLS = {
    "get_decision_context",
    "get_current_decision_report",
    "get_holding",
    "get_account_summary",
    "get_market_quote",
    "get_daily_price_summary",
    "get_technical_snapshot",
    "get_risk_snapshot",
    "get_event_evidence",
    "get_company_announcements",
    "get_company_news",
    "get_business_evidence",
    "get_trade_plan",
    "get_personal_rule",
    "get_market_regime",
    "get_relative_strength",
    "get_previous_decisions",
    "get_recommendation_evaluations",
    "request_user_input",
}

_DESCRIPTIONS = {
    "get_decision_context": "Read the normalized decision context and data-quality state for the current symbol.",
    "get_current_decision_report": "Read the newest saved decision report for a symbol.",
    "get_holding": "Read the user's saved holdings. Use this to verify quantity and cost basis.",
    "get_account_summary": "Read available account cash used by deterministic position sizing.",
    "get_market_quote": "Read the latest cached quote for a symbol.",
    "get_daily_price_summary": "Read up to 60 recent daily price records for a symbol.",
    "get_technical_snapshot": "Read the normalized technical-analysis snapshot already present in the context.",
    "get_risk_snapshot": "Read the cached risk-analysis snapshot for a symbol.",
    "get_event_evidence": "Read normalized news and announcement evidence already present in the context.",
    "get_company_announcements": "Read source-linked formal company announcements, including disclosure time and the original announcement URL. Use for earnings, guidance, dividends, reductions, buybacks, and other disclosures.",
    "get_company_news": "Read source-linked company news with publication times. Treat it as context, and prefer formal announcements when sources conflict.",
    "get_business_evidence": "Read the combined business-evidence bundle: formal announcements, news, publication timing, the user's thesis and market expectation, and relative market context. Use before saying business, industry, event, or time information is missing.",
    "get_trade_plan": "Read the user's saved trade plan for a symbol.",
    "get_personal_rule": "Read the user's saved personal risk rules.",
    "get_market_regime": "Read the current market-regime snapshot from the context.",
    "get_relative_strength": "Read the symbol's relative-strength snapshot from the context.",
    "get_previous_decisions": "Read previous saved decision reports for a symbol.",
    "get_recommendation_evaluations": "Read historical recommendation evaluations for a symbol.",
    "request_user_input": "Ask one to three concise questions only when missing user information materially changes the conclusion.",
}

_NO_ARGUMENT_TOOLS = {"get_account_summary", "get_personal_rule"}


def _parameters(name: str) -> dict[str, object]:
    if name == "request_user_input":
        return {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 3,
                }
            },
            "required": ["questions"],
            "additionalProperties": False,
        }
    if name in _NO_ARGUMENT_TOOLS:
        return {"type": "object", "properties": {}, "additionalProperties": False}
    return {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock symbol. Omit to use the symbol in the active research context.",
            }
        },
        "additionalProperties": False,
    }


def definitions() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": _DESCRIPTIONS[name],
                "parameters": _parameters(name),
            },
        }
        for name in sorted(ALLOWED_TOOLS)
    ]
