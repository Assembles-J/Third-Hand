"""Allowlisted Research Chat tools.

Research tools are read-only or confirmation proposals. They cannot execute a
paper trade, alter ActionPolicy, change formal sizing, or bypass the historical
DecisionReport -> next eligible quote execution boundary.
"""
from __future__ import annotations

ALLOWED_TOOLS: dict[str, str] = {
    "get_current_quote": "读取当前缓存行情",
    "get_daily_history": "读取本地历史日线",
    "request_daily_history_refresh": "申请刷新历史日线；需要确认，不由模型直接执行",
    "get_position_snapshot": "读取当前持仓快照",
    "get_risk_snapshot": "读取当前风险快照",
    "get_company_fundamentals": "读取本地公司/工具元数据",
    "get_announcement_timeline": "读取本地公告时间线",
    "get_company_news": "读取本地公司新闻",
    "get_research_evidence": "读取本地研究证据",
    "get_research_thesis": "读取本地 Research Thesis",
    "get_decision_report": "读取已保存的正式决策报告",
    "propose_data_change": "提出数据修改建议，需要用户确认",
    "request_user_input": "请求用户补充输入",
}


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def definitions() -> list[dict]:
    result = []
    for name, description in ALLOWED_TOOLS.items():
        if name in {
            "get_current_quote", "get_daily_history", "get_position_snapshot",
            "get_risk_snapshot", "get_company_fundamentals", "get_research_evidence",
            "get_research_thesis", "get_decision_report",
        }:
            props = {"symbol": {"type": "string"}}
            if name == "get_daily_history":
                props["limit"] = {"type": "integer", "minimum": 1, "maximum": 240}
            params = _schema(props, ["symbol"])
        elif name == "request_daily_history_refresh":
            params = _schema(
                {
                    "symbol": {"type": "string"},
                    "required_days": {"type": "integer", "minimum": 30, "maximum": 240},
                },
                ["symbol"],
            )
        elif name in {"get_announcement_timeline", "get_company_news"}:
            params = _schema(
                {"symbol": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                ["symbol"],
            )
        elif name == "propose_data_change":
            params = _schema(
                {
                    "target": {"type": "string", "enum": ["holding", "watchlist", "trade_plan"]},
                    "operation": {"type": "string", "enum": ["create", "update", "delete"]},
                    "payload": {"type": "object"},
                },
                ["target", "operation", "payload"],
            )
        else:
            params = _schema(
                {"questions": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}},
                ["questions"],
            )
        result.append({"type": "function", "function": {"name": name, "description": description, "parameters": params}})
    return result
