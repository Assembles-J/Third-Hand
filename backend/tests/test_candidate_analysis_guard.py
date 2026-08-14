import pytest

from app.application_services.candidate.service import CandidateService
from app.infrastructure.database.candidate_repository import CandidateRepository
from app.storage import PortfolioStore


def _service(tmp_path) -> CandidateService:
    return CandidateService(CandidateRepository(PortfolioStore(tmp_path / "candidate-analysis.db")))


def test_deep_analysis_must_start_through_readiness_guard(tmp_path):
    service = _service(tmp_path)
    service.add_manual_candidate(symbol="1810.HK", name="小米集团", research_priority="L3")

    readiness = service.analysis_readiness("1810.HK")
    assert readiness["allowed"] is True
    assert readiness["recommended_analysis_depth"] == "deep_company"
    assert readiness["formal_trade_authority"] is False

    started = service.start_analysis("1810.HK", reason="manual_deep_research")
    assert started["lifecycle_status"] == "ANALYZING"

    with pytest.raises(ValueError, match="analysis_not_ready:analysis_already_running"):
        service.start_analysis("1810.HK")


def test_waiting_trigger_and_cooldown_prevent_repeat_deep_analysis(tmp_path):
    service = _service(tmp_path)
    service.add_manual_candidate(symbol="1810.HK", name="小米集团", research_priority="L3")
    service.start_analysis("1810.HK")
    service.record_analysis_result(
        "1810.HK",
        analysis_version="company-research-v1",
        thesis_hash="thesis-1",
        summary="等待汽车毛利与交付验证",
        lifecycle_status="WAITING_TRIGGER",
        cooldown_until="2099-08-21T09:00:00+08:00",
    )

    readiness = service.analysis_readiness("1810.HK")
    assert readiness["allowed"] is False
    assert readiness["reason"] == "waiting_for_structured_reactivation_trigger"

    with pytest.raises(ValueError, match="waiting_for_structured_reactivation_trigger"):
        service.start_analysis("1810.HK")

    service.transition("1810.HK", lifecycle_status="REACTIVATED", reason="结构化价格条件命中")
    # Transitioning out of WAITING_TRIGGER clears the old cooldown by design:
    # a verified reactivation trigger outranks the time cooldown.
    readiness = service.analysis_readiness("1810.HK")
    assert readiness["allowed"] is True


def test_analysis_result_requires_explicit_analyzing_state(tmp_path):
    service = _service(tmp_path)
    service.add_manual_candidate(symbol="600519", name="贵州茅台", research_priority="L3")

    with pytest.raises(ValueError, match="analysis_result_requires_ANALYZING_state"):
        service.record_analysis_result(
            "600519",
            analysis_version="company-research-v1",
            thesis_hash=None,
            summary="should not be accepted",
            lifecycle_status="WAITING_TRIGGER",
            cooldown_until=None,
        )
