"""Conservative, evidence-based portfolio review; never generates trade orders."""
from __future__ import annotations
from uuid import uuid4

def assess_holdings(holdings, quotes, store, technical_service=None):
    quote_by_symbol = {str(item["symbol"]): item for item in quotes}
    results = []
    for holding in holdings:
        symbol, cost = str(holding["symbol"]), float(holding["average_cost"])
        quote, risk = quote_by_symbol.get(symbol), store.cached_risk(symbol)
        price = quote.get("price") if quote else None
        evidence = []
        trace = []
        technical_snapshot = None
        technical_risk = False
        rules = [rule for rule in store.personal_rules() if rule["enabled"]]
        rule = next((rule for rule in rules if rule["scope"] == "symbol" and rule["symbol"] == symbol), next((rule for rule in rules if rule["scope"] == "global"), None))
        loss_threshold = float(rule["loss_review_percent"]) if rule else 15.0
        volatility_threshold = float(rule["volatility_review_percent"]) if rule else 50.0
        confidence = 35
        if price is None:
            trace.append({"stage": "行情快照", "status": "missing", "detail": "未找到已缓存的行情快照，未使用价格相关规则。"})
            action, reason = "data_insufficient", "未获得可用行情，先核对证券代码和数据源。"
        else:
            trace.append({"stage": "行情快照", "status": "ok", "detail": f"使用 {quote.get('source', '缓存行情')}；现价 {price} {quote.get('currency', '')}；快照时间 {quote.get('retrieved_at', quote.get('as_of', '未知'))}。"})
            confidence += 30
            deviation = round((float(price) - cost) / cost * 100, 2) if cost else None
            evidence.append(f"现价相对成本：{deviation}%")
            if risk:
                evidence.append(f"历史下行概率：{risk['historical_downside_probability']}%，年化波动：{risk['annualized_volatility_percent']}%")
                confidence += 25
                trace.append({"stage": "风险统计", "status": "ok", "detail": f"已使用历史下行概率 {risk['historical_downside_probability']}%，年化波动 {risk['annualized_volatility_percent']}%。"})
            if technical_service:
                try:
                    try:
                        bars = store.daily_prices(symbol) if hasattr(store, "daily_prices") else []
                        technical_snapshot = technical_service.assess(symbol, bars)
                    except TypeError:
                        # Keep custom/test adapters written against the original
                        # one-argument protocol working during the migration.
                        technical_snapshot = technical_service.assess(symbol)
                    evidence.append(
                        f"技术面：{technical_snapshot['trend_label']}；"
                        f"RSI(14) {technical_snapshot['rsi14']}（{technical_snapshot['rsi_state']}）；"
                        f"60 日回撤 {technical_snapshot['drawdown_60d_percent']}%"
                    )
                    confidence += 10
                    trace.append({
                        "stage": "技术指标",
                        "status": "ok",
                        "detail": (
                            f"{technical_snapshot['trend_label']}；RSI(14) {technical_snapshot['rsi14']}；"
                            f"MACD 柱 {technical_snapshot['macd_histogram']}；"
                            f"ATR/收盘 {technical_snapshot['atr_percent']}%；"
                            f"数据截至 {technical_snapshot['as_of']}。"
                        ),
                    })
                    technical_risk = (
                        technical_snapshot["trend"] == "down"
                        and technical_snapshot["drawdown_60d_percent"] <= -12
                    )
                except Exception:
                    trace.append({"stage": "技术指标", "status": "unavailable", "detail": "技术指标暂不可用；本次结论未依赖该项。"})
            if risk and (float(risk["historical_downside_probability"]) >= 20 or float(risk["annualized_volatility_percent"]) >= volatility_threshold):
                action, reason = "risk_review", "历史波动或下行频率偏高，建议复核仓位上限与承受范围。"
            elif deviation is not None and deviation <= -loss_threshold:
                action, reason = "wait_for_confirmation", "成本偏离较大；先核对基本面、公告和风险承受范围，不按单日价格追补。"
            elif technical_risk:
                action, reason = "risk_review", "中期趋势偏弱且近期回撤扩大，建议复核风险暴露与事件证据。"
            else:
                action, reason = "observe", "暂无触发的高风险规则，持续关注公告、风险统计和行情时效。"
        if rule:
            confidence += 10
            trace.append({"stage": "个人规则", "status": "ok", "detail": f"命中{'个股' if rule['scope'] == 'symbol' else '全局'}规则 v{rule['version']}：亏损复核阈值 {loss_threshold}%，波动复核阈值 {volatility_threshold}%。"})
        else:
            trace.append({"stage": "个人规则", "status": "default", "detail": f"未命中已启用个人规则，使用默认阈值：亏损 {loss_threshold}%，波动 {volatility_threshold}%。"})
        results.append({"symbol":symbol,"name":holding["name"],"action":action,"reason":reason,"evidence":evidence,"confidence_percent":min(confidence, 95),"rule_snapshot":rule,"technical_snapshot":technical_snapshot,"disclaimer":"置信度表示证据完整度与规则适用程度，不表示涨跌概率。"})
        results[-1]["analysis_trace"] = trace + [{"stage": "结论生成", "status": "ok", "detail": f"生成“{action}”结论；证据完整度 {min(confidence, 95)}%。"}]
    return {"id":str(uuid4()),"items":results}
