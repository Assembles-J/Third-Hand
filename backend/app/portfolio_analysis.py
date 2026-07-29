"""Conservative, evidence-based portfolio review; never generates trade orders."""
from __future__ import annotations
from uuid import uuid4

def assess_holdings(holdings, quotes, store):
    quote_by_symbol = {str(item["symbol"]): item for item in quotes}
    results = []
    for holding in holdings:
        symbol, cost = str(holding["symbol"]), float(holding["average_cost"])
        quote, risk = quote_by_symbol.get(symbol), store.cached_risk(symbol)
        price = quote.get("price") if quote else None
        evidence = []
        rules = [rule for rule in store.personal_rules() if rule["enabled"]]
        rule = next((rule for rule in rules if rule["scope"] == "symbol" and rule["symbol"] == symbol), next((rule for rule in rules if rule["scope"] == "global"), None))
        loss_threshold = float(rule["loss_review_percent"]) if rule else 15.0
        volatility_threshold = float(rule["volatility_review_percent"]) if rule else 50.0
        confidence = 35
        if price is None:
            action, reason = "data_insufficient", "未获得可用行情，先核对证券代码和数据源。"
        else:
            confidence += 30
            deviation = round((float(price) - cost) / cost * 100, 2) if cost else None
            evidence.append(f"现价相对成本：{deviation}%")
            if risk:
                evidence.append(f"历史下行概率：{risk['historical_downside_probability']}%，年化波动：{risk['annualized_volatility_percent']}%")
                confidence += 25
            if risk and (float(risk["historical_downside_probability"]) >= 20 or float(risk["annualized_volatility_percent"]) >= volatility_threshold):
                action, reason = "risk_review", "历史波动或下行频率偏高，建议复核仓位上限与承受范围。"
            elif deviation is not None and deviation <= -loss_threshold:
                action, reason = "wait_for_confirmation", "成本偏离较大；先核对基本面、公告和风险承受范围，不按单日价格追补。"
            else:
                action, reason = "observe", "暂无触发的高风险规则，持续关注公告、风险统计和行情时效。"
        if rule: confidence += 10
        results.append({"symbol":symbol,"name":holding["name"],"action":action,"reason":reason,"evidence":evidence,"confidence_percent":min(confidence, 95),"rule_snapshot":rule,"disclaimer":"置信度表示证据完整度与规则适用程度，不表示涨跌概率。"})
    return {"id":str(uuid4()),"items":results}
