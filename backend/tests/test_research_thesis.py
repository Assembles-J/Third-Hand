from app.decision_models import ResearchClaim, ResearchReport
from app.research_thesis import ResearchThesisService
from app.storage import PortfolioStore
from app.time_utils import beijing_now


def _report(report_id: str, symbol: str = "600519", evidence_ids: tuple[str, ...] = ("e1",)) -> ResearchReport:
    claim = ResearchClaim(
        claim_id=f"claim.{report_id}", statement="待继续复核的研究观察", evidence_type="INFERENCE",
        supporting_evidence_ids=evidence_ids, missing_evidence=("更多正式披露",), confidence_band="low",
    )
    return ResearchReport.model_validate({
        "report_id": report_id, "context_id": "ctx", "symbol": symbol, "generated_at": beijing_now(),
        "evidence": [{"evidence_id": item, "category": "event", "direction": "neutral", "strength": 0.1,
                      "title": "事件", "description": "可追溯事件", "source": "test", "fresh": True} for item in evidence_ids],
        "claims": [claim.model_dump()],
        "data_quality": {"status": "ready", "score_percent": 100, "missing_fields": [], "stale_fields": [], "warnings": [], "source_freshness": [], "action_gates": []},
        "report_status": "ready", "input_hash": "hash",
    })


def test_thesis_versions_keep_prior_version_and_never_emit_action():
    service = ResearchThesisService()
    first = service.create(_report("r1"))
    second = service.create(_report("r2", evidence_ids=("e1", "e2")), thesis_id=first.thesis_id, prior=first)

    assert first.version == 1
    assert second.version == 2
    assert second.prior_version_id == f"{first.thesis_id}:1"
    assert second.research_only is True
    assert not hasattr(second, "action")
    assert service.review_summary(first, second)["new_evidence_ids"] == ["e2"]


def test_thesis_version_persists_immutably(tmp_path):
    store = PortfolioStore(tmp_path / "thesis.db")
    service = ResearchThesisService()
    first = service.create(_report("r1"))
    store.save_research_thesis(first.model_dump(mode="json"))
    second = service.create(_report("r2", evidence_ids=("e1", "e2")), thesis_id=first.thesis_id, prior=first)
    store.save_research_thesis(second.model_dump(mode="json"))

    assert store.research_thesis(first.thesis_id, version=1)["report_id"] == "r1"
    assert store.research_thesis(first.thesis_id)["report_id"] == "r2"
