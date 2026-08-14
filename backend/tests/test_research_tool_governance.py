from types import SimpleNamespace

import pytest

from app.research_chat.tool_executor import ToolExecutor
from app.research_chat.tool_registry import ALLOWED_TOOLS, definitions
from app.storage import PortfolioStore


def test_research_tool_registry_has_no_direct_paper_trade_tools():
    names = {item["function"]["name"] for item in definitions()}

    assert "paper_add_position" not in names
    assert "paper_reduce_position" not in names
    assert "paper_add_position" not in ALLOWED_TOOLS
    assert "paper_reduce_position" not in ALLOWED_TOOLS


def test_removed_paper_trade_tool_cannot_mutate_paper_ledger(tmp_path):
    store = PortfolioStore(tmp_path / "research-tool-governance.db")
    executor = ToolExecutor(store)
    context = SimpleNamespace(symbol="600519")
    before = store.paper_account()

    with pytest.raises(ValueError, match="tool_not_allowed"):
        executor.execute(
            "paper_add_position",
            {"symbol": "600519", "quantity": 100},
            context,
        )

    after = store.paper_account()
    assert after == before


def test_data_change_tool_remains_confirmation_only(tmp_path):
    store = PortfolioStore(tmp_path / "research-tool-proposal.db")
    executor = ToolExecutor(store)
    context = SimpleNamespace(symbol="600519")

    result = executor.execute(
        "propose_data_change",
        {
            "entity": "trade_plan",
            "operation": "update",
            "summary": "建议更新研究计划，等待用户确认",
        },
        context,
    )

    assert result["confirmation_required"] is True
    assert result["automatic_execution"] is False
