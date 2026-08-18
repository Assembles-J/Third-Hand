from datetime import datetime, timedelta, timezone
from uuid import uuid4

import app.storage as storage_module
from app.decision_context import DecisionContextBuilder
from app.evidence_engine import EvidenceEngine
from app.paper_execution_contract import explicit_order_quantity, project_paper_holdings
from app.position_cap_policy import effective_position_cap_percent
from app.position_sizing import PositionSizingEngine
from app.storage import PortfolioStore


def _seed_decision_inputs(store: PortfolioStore, *, cap: float, holding_quantity: float = 0.0, cash: float = 10_000.0) -> None:
    if holding_quantity > 0:
        store.add("holding-1", "600519", "test", holding_quantity, 10)
    store.save_available_cash(cash)
    store.save_quotes([{
        "symbol": "600519", "price": 10, "volume": 20_000, "currency": "CNY",
        "source": "test", "as_of": "2026-08-18T10:00:00+08:00",
        "retrieved_at": "2026-08-18T10:00:01+08:00",
    }])
    start = datetime(2026, 5, 1, tzinfo=timezone.utc).date()
    store.save_daily_prices("600519", [
        {
            "trading_date": (start + timedelta(days=index)).isoformat(),
            "open": 10, "close": 10, "high": 11, "low": 9, "source": "test",
        }
        for index in range(60)
    ])
    store.save_risk({
        "symbol": "600519", "as_of": "2026-08-18", "sample_count": 60,
        "historical_downside_probability": 10, "annualized_volatility_percent": 20,
        "risk_level": "low",
    })
    store.save_trade_plan({
        "id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test",
        "market_expectation": "test", "catalysts": [], "entry_condition": "entry",
        "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit",
        "max_position_percent": 50, "risk_budget_percent": 3, "invalidation_price": 9,
        "enabled": True, "version": 1,
    })
    store.save_personal_rule({
        "id": "rule-1", "scope": "global", "symbol": None,
        "max_position_percent": cap, "loss_review_percent": 15,
        "volatility_review_percent": 50, "enabled": True, "version": 1,
        "updated_at": "2026-08-18T10:00:00+08:00",
    })
    store.save_instrument_metadata({
        "symbol": "600519", "market": "CN", "currency": "CNY", "lot_size": 100,
        "price_tick": "0.01", "source": "test", "as_of": "2026-08-18",
    })


def test_personal_cap_is_the_same_authority_for_open_evidence_and_reduce(tmp_path):
    flat_store = PortfolioStore(tmp_path / "flat.db")
    _seed_decision_inputs(flat_store, cap=10, holding_quantity=0, cash=10_000)
    flat = DecisionContextBuilder(flat_store).build("600519")

    assert effective_position_cap_percent(flat) == 10
    open_size = PositionSizingEngine().size(flat, "OPEN")
    assert open_size.status == "ready"
    assert open_size.target_position_percent <= 10
    assert open_size.target_quantity == 100

    held_store = PortfolioStore(tmp_path / "held.db")
    _seed_decision_inputs(held_store, cap=10, holding_quantity=200, cash=8_000)
    held = DecisionContextBuilder(held_store).build("600519")
    evidence = {item.evidence_id: item for item in EvidenceEngine().build(held)}

    assert evidence["position.above_max"].threshold == 10
    reduce_size = PositionSizingEngine().size(held, "REDUCE")
    assert reduce_size.status == "ready"
    assert reduce_size.quantity_by_position_cap == 100
    assert reduce_size.suggested_quantity == 100
    assert reduce_size.target_quantity == 100
    assert reduce_size.target_position_percent <= 10


def test_zero_suggested_quantity_never_falls_back_to_target_position_quantity():
    assert explicit_order_quantity({"suggested_quantity": 0.0, "target_quantity": 1500.0}) == 0.0
    assert explicit_order_quantity({"suggested_quantity": None, "target_quantity": 1500.0}) == 0.0
    assert explicit_order_quantity({"suggested_quantity": 800.0, "target_quantity": 200.0}) == 800.0


def test_projected_paper_position_preserves_first_entry_episode_after_add(tmp_path, monkeypatch):
    store = PortfolioStore(tmp_path / "episode-projection.db")
    store.save_paper_account(20_000)
    day_one = datetime(2026, 8, 18, 10, tzinfo=timezone(timedelta(hours=8)))
    day_two = datetime(2026, 8, 19, 10, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)

    entry_snapshot = {
        "episode_id": "entry-episode-1",
        "evidence_snapshot_hash": "atomic-entry-hash",
        "research_assessment_hash": "research-entry-hash",
        "risk_state": {"risk_level": "low"},
        "technical_state": {"technical_state": ["up", "bullish", "neutral"]},
        "market_regime": {"market_regime": ["ready", "supportive"]},
        "event_state": {"event_state": []},
        "entry_price": 10,
    }
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="test", side="BUY", quantity=100,
        price=10, decision_id="entry-decision-1", reason="entry", entry_snapshot=entry_snapshot,
    )

    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_two)
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="test", side="BUY", quantity=100,
        price=11, decision_id="add-decision-1", reason="add",
        entry_snapshot={"episode_id": "must-not-overwrite"},
    )

    _seed_decision_inputs(store, cap=20, holding_quantity=0, cash=0)
    paper_account = store.paper_account()
    holdings = project_paper_holdings(store, paper_account)
    projected = holdings[0]

    assert projected["entry_episode_id"] == "entry-episode-1"
    assert projected["entry_decision_id"] == "entry-decision-1"
    assert projected["entry_evidence_snapshot_hash"] == "atomic-entry-hash"
    assert projected["entry_research_assessment_hash"] == "research-entry-hash"
    assert projected["entry_risk_state"] == {"risk_level": "low"}
    assert projected["entry_price"] == 10
    assert projected["created_at"] == day_one.isoformat()

    context = DecisionContextBuilder(store).build(
        "600519",
        holdings_override=holdings,
        available_cash_override=float(paper_account["available_cash"]),
    )
    assert context.position is not None
    assert context.position.entry_episode_id == "entry-episode-1"
    assert context.position.entry_decision_id == "entry-decision-1"
    assert context.position.entry_evidence_snapshot_hash == "atomic-entry-hash"
    assert context.position.entry_research_assessment_hash == "research-entry-hash"
    assert context.position.entry_risk_state == {"risk_level": "low"}
    assert context.position.entry_price == 10
    assert context.position.opened_at == day_one.isoformat()


def test_mixed_t1_exit_keeps_order_within_sellable_quantity(tmp_path):
    store = PortfolioStore(tmp_path / "mixed-t1.db")
    _seed_decision_inputs(store, cap=20, holding_quantity=100, cash=9_000)
    context = DecisionContextBuilder(store).build("600519")
    mixed = context.position.model_copy(update={
        "quantity": 1_000.0,
        "sellable_quantity": 800.0,
        "locked_quantity": 200.0,
        "next_eligible_sell_at": "2026-08-19T09:30:00+08:00",
    })

    result = PositionSizingEngine().size(context.model_copy(update={"position": mixed}), "EXIT")

    assert result.suggested_quantity == 800.0
    assert result.max_executable_quantity == 800.0
    assert explicit_order_quantity(result.model_dump(mode="json")) == 800.0
