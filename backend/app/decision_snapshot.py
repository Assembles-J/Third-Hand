"""Immutable, source-linked evidence snapshot for a portfolio review run."""
from __future__ import annotations


def build_decision_snapshot(holding, quote, risk, rule, content_items, action: str, trade_plan=None, market_regime=None, relative_strength=None) -> dict[str, object]:
    symbol = str(holding["symbol"]).strip().upper()
    events = []
    for item in content_items:
        if symbol not in {str(value).strip().upper() for value in item.get("related_symbols", [])}:
            continue
        ai = item.get("ai_analysis") or {}
        events.append({
            "id": str(item.get("id", "")), "title": str(item.get("title", "未命名事件")),
            "impact": str(ai.get("impact", "uncertain")),
            "summary": str(ai.get("summary") or item.get("explanation") or "待核验的来源事件"),
            "source_url": item.get("source_url"), "published_at": item.get("published_at"),
        })
        if len(events) == 5:
            break
    quote_snapshot = {key: quote.get(key) for key in (
        "price", "change_percent", "volume", "amount", "source", "as_of", "retrieved_at",
        "is_realtime", "delay_seconds", "freshness_note", "refresh_status",
    )} if quote else None
    missing = []
    if not quote or quote.get("price") is None:
        missing.append("可用行情快照")
    if not risk:
        missing.append("历史风险样本")
    if not events:
        missing.append("已关联的新闻或公告")
    if not rule:
        missing.append("个人仓位规则（当前使用默认阈值）")
    if not trade_plan or not trade_plan.get("enabled"):
        missing.append("已启用的交易计划")
    candidates = {
        "risk_review": "若确认风险承受范围或个人仓位上限已被突破，可按你的规则把仓位降回上限以内；先核验事件原文。",
        "wait_for_confirmation": "等待公告、基本面或量价条件得到确认；不因单日价格波动追补仓位。",
        "observe": "维持观察；若新增正式公告或风险指标触发个人阈值，再重新复核。",
        "data_insufficient": "先补全行情与来源证据；当前不生成仓位调整候选。",
    }
    plan_condition = {
        "risk_review": "reduce_condition", "wait_for_confirmation": "entry_condition",
        "observe": "add_condition", "data_insufficient": "entry_condition",
    }.get(action)
    return {
        "symbol": symbol, "holding": {"average_cost": holding.get("average_cost"), "quantity": holding.get("quantity")},
        "quote": quote_snapshot, "risk": risk, "rule": rule, "event_evidence": events,
        "missing_evidence": missing, "evidence_completeness_percent": max(20, 100 - len(missing) * 18),
        "candidate_action": candidates.get(action, candidates["observe"]),
        "trade_plan": ({
            "horizon": trade_plan.get("horizon"), "thesis": trade_plan.get("thesis"),
            "catalysts": trade_plan.get("catalysts", []), "condition_to_verify": trade_plan.get(plan_condition),
            "max_position_percent": trade_plan.get("max_position_percent"),
            "risk_budget_percent": trade_plan.get("risk_budget_percent"),
        } if trade_plan and trade_plan.get("enabled") else None),
        "market_regime": market_regime,
        "relative_strength": relative_strength,
        "confidence_definition": "该分数衡量证据完整度，不代表价格涨跌或操作正确概率。",
    }
