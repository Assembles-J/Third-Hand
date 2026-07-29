"""Conservative, evidence-based portfolio review; never generates trade orders."""
from __future__ import annotations

def assess_holdings(holdings, quotes, store):
    quote_by_symbol = {str(item["symbol"]): item for item in quotes}
    results = []
    for holding in holdings:
        symbol, cost = str(holding["symbol"]), float(holding["average_cost"])
        quote, risk = quote_by_symbol.get(symbol), store.cached_risk(symbol)
        price = quote.get("price") if quote else None
        evidence = []
        if price is None:
            action, reason = "data_insufficient", "未获得可用行情，先核对证券代码和数据源。"
        else:
            deviation = round((float(price) - cost) / cost * 100, 2) if cost else None
            evidence.append(f"现价相对成本：{deviation}%")
            if risk:
                evidence.append(f"历史下行概率：{risk['historical_downside_probability']}%，年化波动：{risk['annualized_volatility_percent']}%")
            if risk and (float(risk["historical_downside_probability"]) >= 20 or float(risk["annualized_volatility_percent"]) >= 50):
                action, reason = "risk_review", "历史波动或下行频率偏高，建议复核仓位上限与承受范围。"
            elif deviation is not None and deviation <= -15:
                action, reason = "wait_for_confirmation", "成本偏离较大；先核对基本面、公告和风险承受范围，不按单日价格追补。"
            else:
                action, reason = "observe", "暂无触发的高风险规则，持续关注公告、风险统计和行情时效。"
        results.append({"symbol":symbol,"name":holding["name"],"action":action,"reason":reason,"evidence":evidence,"disclaimer":"规则化信息复核，不构成买卖建议或收益承诺。"})
    return {"items":results}
