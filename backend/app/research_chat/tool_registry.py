"""The only callable tools are read-only facts and a structured clarification request."""
from __future__ import annotations
ALLOWED_TOOLS={"get_decision_context","get_current_decision_report","get_holding","get_account_summary","get_market_quote","get_daily_price_summary","get_technical_snapshot","get_risk_snapshot","get_event_evidence","get_trade_plan","get_personal_rule","get_market_regime","get_relative_strength","get_previous_decisions","get_recommendation_evaluations","request_user_input"}
def definitions():
 return [{"type":"function","function":{"name":name,"description":"Read-only Third-Hand research data." if name!="request_user_input" else "Ask up to three material clarification questions.","parameters":{"type":"object","properties":{"symbol":{"type":"string"},"questions":{"type":"array","items":{"type":"string"}}},"additionalProperties":False}}} for name in sorted(ALLOWED_TOOLS)]
