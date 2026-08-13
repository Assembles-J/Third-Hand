from datetime import timedelta

from app.action_policy import ActionPolicyEngine
from app.data_quality import summarize_data_quality
from app.decision_context import DecisionContextBuilder
from app.evidence_engine import EvidenceEngine
from app.execution_precheck import validate_daily_execution
from app.freshness import evaluate_freshness
from app.storage import PortfolioStore
from app.time_utils import beijing_now


def test_freshness_never_treats_missing_timestamp_as_fresh():
    result = evaluate_freshness("quote", as_of=None, retrieved_at=None, max_age_seconds=60)

    assert result.status == "unknown"
    assert result.reason == "timestamp_missing"


def test_stale_quote_blocks_open_and_add_but_not_defensive_review():
    now = beijing_now()
    quality = summarize_data_quality(
        has_quote=True, daily_bar_count=60, total_assets_available=True, plan_enabled=True,
        has_risk=True, has_market_regime=True, has_relative_strength=True, has_events=True,
        has_instrument=True, has_position=True, has_personal_rule=True,
        quote_as_of=(now - timedelta(days=3)).isoformat(), quote_retrieved_at=(now - timedelta(days=3)).isoformat(),
        daily_bar_as_of=now.date().isoformat(), risk_as_of=now.date().isoformat(),
        market_as_of=now.isoformat(), market_retrieved_at=now.isoformat(),
    )
    gates = {item.action: item for item in quality.action_gates}

    assert quality.status == "degraded"
    assert gates["OPEN"].permission == "blocked"
    assert gates["ADD"].permission == "blocked"
    assert gates["REDUCE"].permission == "research_only"


def test_watchlist_state_is_not_an_input_to_policy(tmp_path):
    store = PortfolioStore(tmp_path / "policy-freshness.db")
    store.save_available_cash(1_000)
    now = beijing_now()
    store.save_quotes([{ "symbol": "600519", "price": 10, "volume": 10_000, "currency": "CNY", "source": "test", "as_of": now.isoformat(), "retrieved_at": now.isoformat() }])
    store.save_daily_prices("600519", [{"trading_date": (now.date() - timedelta(days=60 - index)).isoformat(), "open": 10, "close": 10, "high": 11, "low": 9, "source": "test"} for index in range(60)])
    store.save_risk({"symbol": "600519", "as_of": now.date().isoformat(), "sample_count": 60, "historical_downside_probability": 10, "annualized_volatility_percent": 20, "risk_level": "low"})
    store.save_instrument_metadata({"symbol": "600519", "market": "CN", "currency": "CNY", "lot_size": 100, "price_tick": "0.01", "source": "test", "as_of": now.date().isoformat()})

    before = DecisionContextBuilder(store).build("600519")
    store.save_watchlist_item("600519", "test")
    after = DecisionContextBuilder(store).build("600519")

    assert ActionPolicyEngine().evaluate(before, EvidenceEngine().build(before))[0].action == ActionPolicyEngine().evaluate(after, EvidenceEngine().build(after))[0].action
    assert before.data_quality == after.data_quality


def test_daily_execution_waits_for_a_later_market_session():
    report = {
        "action": "OPEN", "generated_at": "2026-08-12T16:00:00+08:00", "market_as_of": "2026-08-12",
        "data_quality": {"action_gates": [{"action": "OPEN", "permission": "allowed"}]},
    }

    assert validate_daily_execution(report, {"price": 10, "as_of": "2026-08-12"}).reason == "execution_not_due_next_market_session"
    assert validate_daily_execution(report, {"price": 10, "as_of": "2026-08-13"}).allowed is True


def test_llm_news_impact_is_research_only_and_cannot_create_policy_event(tmp_path):
    store = PortfolioStore(tmp_path / "llm-event-gate.db")
    now = beijing_now()
    store.save_available_cash(10_000)
    store.save_quotes([{ "symbol": "600519", "price": 10, "volume": 10_000, "currency": "CNY", "source": "test", "as_of": now.isoformat(), "retrieved_at": now.isoformat() }])
    store.save_daily_prices("600519", [{"trading_date": (now.date() - timedelta(days=60 - index)).isoformat(), "open": 10, "close": 10, "high": 11, "low": 9, "source": "test"} for index in range(60)])
    store.save_risk({"symbol": "600519", "as_of": now.date().isoformat(), "historical_downside_probability": 10, "annualized_volatility_percent": 20})
    store.save_instrument_metadata({"symbol": "600519", "market": "CN", "currency": "CNY", "lot_size": 100, "price_tick": "0.01", "source": "test", "as_of": now.date().isoformat()})
    store.save_content([{ "id": "news-1", "related_symbols": ["600519"], "title": "测试新闻", "source_name": "test", "published_at": now.isoformat(), "ai_analysis": {"impact": "negative", "summary": "模型判断负面"} }])

    context = DecisionContextBuilder(store).build("600519")
    evidence_ids = {item.evidence_id for item in EvidenceEngine().build(context)}

    assert context.events[0].impact == "uncertain"
    assert not any(item.startswith("event.negative.") for item in evidence_ids)
