"""Bounded local implementation of the tool whitelist."""
from __future__ import annotations
import json
from .tool_registry import ALLOWED_TOOLS
class ToolExecutor:
 def __init__(self,store):self.store=store
 def execute(self,name,args,context):
  if name not in ALLOWED_TOOLS:raise ValueError("tool_not_allowed")
  symbol=str(args.get("symbol") or context.symbol).upper()
  if name=="request_user_input":
   questions=args.get("questions") or []
   if not isinstance(questions,list) or not 1<=len(questions)<=3:raise ValueError("tool_invalid_arguments")
   return {"clarification":True,"questions":[str(q)[:240] for q in questions]}
  mapping={"get_decision_context":context.model_dump(mode="json"),"get_holding":self.store.list(),"get_account_summary":self.store.available_cash(),"get_market_quote":self.store.cached_quotes([symbol]),"get_daily_price_summary":self.store.daily_prices(symbol,60),"get_risk_snapshot":self.store.cached_risk(symbol),"get_trade_plan":self.store.trade_plan(symbol),"get_personal_rule":self.store.personal_rules(),"get_previous_decisions":self.store.decision_reports(symbol),"get_recommendation_evaluations":self.store.recommendations(symbol),"get_event_evidence":[e.model_dump(mode="json") for e in context.events],"get_technical_snapshot":context.technical.model_dump(mode="json") if context.technical else None,"get_market_regime":context.market_regime.model_dump(mode="json") if context.market_regime else None,"get_relative_strength":context.relative_strength.model_dump(mode="json") if context.relative_strength else None,"get_current_decision_report":(self.store.decision_reports(symbol,1) or [None])[0]}
  result=mapping.get(name)
  encoded=json.dumps(result,ensure_ascii=False,default=str)
  if len(encoded)>12000:result={"truncated":True,"summary":encoded[:12000]}
  return result
