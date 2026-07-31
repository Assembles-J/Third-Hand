from app.storage import PortfolioStore


def test_trade_plan_upserts_by_symbol_and_keeps_conditions(tmp_path):
    store = PortfolioStore(tmp_path / "plans.db")
    plan = {
        "id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "需求改善且行业景气向上。",
        "market_expectation": "市场担心增速回落。", "catalysts": ["季度报告", "行业数据"],
        "benchmark_symbol": "sh000300", "benchmark_name": "沪深300",
        "entry_condition": "守住关键支撑且量能稳定。", "add_condition": "突破后持续放量。",
        "reduce_condition": "利好落地后不涨。", "exit_condition": "基本逻辑失效或有效跌破。",
        "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1,
    }
    first = store.save_trade_plan(plan)
    second = store.save_trade_plan({**plan, "id": "plan-2", "thesis": "更新后的波段逻辑。", "version": 1})

    assert first["catalysts"] == ["季度报告", "行业数据"]
    assert second["version"] == 2
    assert store.trade_plan("600519")["thesis"] == "更新后的波段逻辑。"
    assert store.trade_plan("600519")["benchmark_symbol"] == "sh000300"
