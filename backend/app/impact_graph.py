"""Build a small, source-linked impact topology around a user's holdings."""
from __future__ import annotations

from app.time_utils import beijing_now


def build_impact_graph(holdings, quotes, store, *, symbol: str | None = None) -> dict[str, object]:
    requested = symbol.strip().upper() if symbol else None
    selected = [item for item in holdings if not requested or str(item["symbol"]).upper() == requested]
    quote_by_symbol = {str(item["symbol"]).upper(): item for item in quotes}
    nodes, edges = [], []

    def node(node_id, kind, label, detail, **extra):
        nodes.append({"id": node_id, "kind": kind, "label": label, "detail": detail, **extra})

    for holding in selected:
        stock = str(holding["symbol"]).upper()
        holding_id = f"holding:{stock}"
        node(holding_id, "holding", str(holding["name"]), f"成本 {float(holding['average_cost']):.2f} · 数量 {float(holding['quantity']):g}", symbol=stock)
        quote = quote_by_symbol.get(stock)
        if quote and quote.get("price") is not None:
            price = float(quote["price"])
            change = (price / float(holding["average_cost"]) - 1) * 100 if holding["average_cost"] else 0
            quote_id = f"quote:{stock}"
            node(quote_id, "market", f"现价 {price:.2f}", f"相对成本 {change:+.1f}% · 成交量 {quote.get('volume') or '未提供'}", symbol=stock, as_of=quote.get("as_of"), source=quote.get("source"))
            edges.append({"source": quote_id, "target": holding_id, "relation": "影响持仓市值", "direction": "neutral", "weight": 1.0})
        risk = store.cached_risk(stock)
        if risk:
            risk_id = f"risk:{stock}"
            node(risk_id, "risk", f"历史风险：{risk.get('risk_level', '未知')}", f"5日下行频率 {risk.get('historical_downside_probability', '—')}% · 年化波动 {risk.get('annualized_volatility_percent', '—')}%", symbol=stock, as_of=risk.get("as_of"))
            edges.append({"source": risk_id, "target": holding_id, "relation": "提示风险暴露", "direction": "negative", "weight": 0.8})
        for content in store.cached_content([stock], limit=30)[:6]:
            analysis = content.get("ai_analysis") or {}
            impact = str(analysis.get("impact", "uncertain"))
            direction = impact if impact in {"positive", "negative", "neutral"} else "uncertain"
            event_id = f"event:{content['id']}"
            node(event_id, "event", str(content.get("title", "未命名事件")), str(analysis.get("summary") or content.get("explanation") or "待核验的来源事件"), symbol=stock, source_url=content.get("source_url"), published_at=content.get("published_at"), confidence=analysis.get("confidence") or content.get("confidence"))
            edges.append({"source": event_id, "target": holding_id, "relation": "事件影响", "direction": direction, "weight": float(content.get("confidence") or 0.5)})
    return {"generated_at": beijing_now().isoformat(), "focus_symbol": requested, "nodes": nodes, "edges": edges, "disclaimer": "关系图展示来源事件与已知风险/行情之间的关联，不代表因果证明或交易建议。"}
