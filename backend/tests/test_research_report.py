import pytest

from app.decision_context import DecisionContextBuilder
from app.evidence_engine import EvidenceEngine
from app.decision_models import ResearchClaim
from app.research_report import ResearchReportBuilder
from app.storage import PortfolioStore


def _context(tmp_path):
    store = PortfolioStore(tmp_path / "research-report.db")
    store.save_available_cash(10_000)
    store.save_quotes([{ "symbol": "600519", "price": 10, "volume": 10_000, "currency": "CNY", "source": "test", "as_of": "2026-08-13", "retrieved_at": "2026-08-13T15:00:00+08:00" }])
    store.save_daily_prices("600519", [{"trading_date": f"2026-08-{index + 1:02d}", "open": 10, "close": 10, "high": 11, "low": 9, "source": "test"} for index in range(60)])
    store.save_risk({"symbol": "600519", "as_of": "2026-08-13", "historical_downside_probability": 10, "annualized_volatility_percent": 20})
    store.save_instrument_metadata({"symbol": "600519", "market": "CN", "currency": "CNY", "lot_size": 100, "price_tick": "0.01", "source": "test", "as_of": "2026-08-13"})
    return DecisionContextBuilder(store).build("600519")


def test_research_report_is_read_only_claims_with_traceable_evidence(tmp_path):
    context = _context(tmp_path)
    report = ResearchReportBuilder(EvidenceEngine()).build(context)
    known = {item.evidence_id for item in report.evidence}

    assert report.research_only is True
    assert report.claims
    assert all(set(claim.supporting_evidence_ids + claim.counter_evidence_ids).issubset(known) for claim in report.claims)
    assert not hasattr(report, "action")


def test_research_claim_validator_rejects_inference_without_counter_or_missing():
    with pytest.raises(ValueError, match="research_inference_requires_counter_or_missing"):
        ResearchReportBuilder._validate([ResearchClaim(claim_id="bad", statement="未经反证的推断", evidence_type="INFERENCE", supporting_evidence_ids=(), confidence_band="low")], set())
