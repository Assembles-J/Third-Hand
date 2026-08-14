from app.decision_context import DecisionContextBuilder
from app.evidence_engine import EvidenceEngine
from app.storage import PortfolioStore


class TechnicalFixture:
    def assess(self, _symbol, _bars):
        return {"as_of": "2026-07-31", "sample_count": 60, "trend": "down", "trend_label": "bearish", "sma20": 12, "sma60": 13, "rsi14": 75, "rsi_state": "hot", "macd_histogram": -0.3, "atr_percent": 5, "drawdown_60d_percent": -16}


def _bars():
    return [{"trading_date": f"2026-06-{index + 1:02d}", "open": 11, "close": 10, "high": 12, "low": 9, "source": "test"} for index in range(60)]


def _context(tmp_path):
    store = PortfolioStore(tmp_path / "evidence.db")
    store.add("holding-1", "600519", "test", 100, 14)
    store.save_available_cash(20)
    store.save_quotes([{"symbol": "600519", "price": 10, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", _bars())
    store.save_risk({"symbol": "600519", "as_of": "2026-07-31", "sample_count": 60, "historical_downside_probability": 25, "annualized_volatility_percent": 55, "risk_level": "high"})
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1, "structured_conditions": [{"trigger": "entry", "field": "close", "operator": "between", "value": [9, 11]}]})
    store.save_personal_rule({"id": "rule-1", "scope": "global", "symbol": None, "max_position_percent": 8, "loss_review_percent": 15, "volatility_review_percent": 50, "enabled": True, "version": 1, "updated_at": "2026-07-31T10:00:00+08:00"})
    store.save_content([{ "id": "notice-1", "title": "negative event", "source_name": "official", "source_url": "https://example.com/notice", "published_at": "2026-07-31T09:00:00+08:00", "related_symbols": ["600519"], "explanation": "test", "ai_analysis": {"impact": "negative", "summary": "negative"}}])
    return DecisionContextBuilder(store, TechnicalFixture()).build("600519")


def test_evidence_engine_emits_deterministic_traceable_unique_evidence(tmp_path):
    context = _context(tmp_path)
    first = EvidenceEngine().build(context)
    second = EvidenceEngine().build(context)
    ids = [item.evidence_id for item in first]

    assert first == second
    assert len(ids) == len(set(ids))
    # Event evidence is directionally neutral by design (cached AI analysis is
    # research-only), and editable trade-plan templates are excluded from the
    # signal path, so neither "event.negative.*" nor "plan.entry_condition_met"
    # is emitted.
    assert {"position.above_max", "position.loss_exceeds_review_threshold", "trend.below_sma20_and_sma60", "momentum.rsi_hot", "momentum.macd_negative", "volatility.atr_high", "risk.historical_downside_high", "risk.annualized_volatility_high", "event.uncertain.notice-1"}.issubset(ids)
    event = next(item for item in first if item.evidence_id == "event.uncertain.notice-1")
    assert event.source_reference == "https://example.com/notice"
    assert next(item for item in first if item.evidence_id == "position.above_max").strength == .9
