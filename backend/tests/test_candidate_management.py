from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.v1.candidate.router import create_candidate_router
from app.application_services.candidate.service import CandidateService
from app.infrastructure.database.candidate_repository import CandidateRepository
from app.storage import PortfolioStore


def _service(tmp_path) -> CandidateService:
    store = PortfolioStore(tmp_path / "candidate.db")
    return CandidateService(CandidateRepository(store))


def test_manual_candidate_is_research_only_and_audited(tmp_path):
    service = _service(tmp_path)

    candidate = service.add_manual_candidate(
        symbol="1810.HK",
        name="小米集团",
        research_priority="L3",
        reason="长期跟踪智能汽车与手机/IoT协同",
    )

    assert candidate["symbol"] == "1810.HK"
    assert candidate["research_priority"] == "L3"
    assert candidate["lifecycle_status"] == "NEW"
    assert candidate["formal_trade_authority"] is False
    assert any(source["source_type"] == "USER_ADDED" for source in candidate["sources"])
    assert any(event["event_type"] == "manual_candidate_added" for event in candidate["events"])


def test_waiting_trigger_cannot_jump_directly_to_open_ready(tmp_path):
    service = _service(tmp_path)
    service.add_manual_candidate(symbol="600519", name="贵州茅台")
    service.transition("600519", lifecycle_status="WAITING_TRIGGER", reason="等待更合理估值")

    with pytest.raises(ValueError, match="transition_not_allowed"):
        service.transition("600519", lifecycle_status="OPEN_READY_RESEARCH")

    reactivated = service.transition("600519", lifecycle_status="REACTIVATED", reason="价格条件命中")
    assert reactivated["lifecycle_status"] == "REACTIVATED"


def test_activation_rule_is_structured_and_never_policy_authority(tmp_path):
    service = _service(tmp_path)
    service.add_manual_candidate(symbol="600519", name="贵州茅台")

    rule = service.add_activation_rule(
        "600519",
        rule_type="PRICE",
        metric="last_price",
        operator="<=",
        value=1200,
        reason="进入预先定义的研究价格区间",
        source="ai_research_proposal",
    )

    assert rule["rule_type"] == "PRICE"
    assert rule["metric"] == "last_price"
    assert rule["operator"] == "<="
    assert rule["value"] == 1200
    assert rule["usage_scope"] == "RESEARCH_ONLY"

    with pytest.raises(ValueError, match="activation metric"):
        service.add_activation_rule(
            "600519",
            rule_type="EVENT",
            metric="",
            operator="exists",
            value=None,
            reason="新闻足够利好",
        )


def test_analysis_result_persists_cooldown_and_thesis_lineage(tmp_path):
    service = _service(tmp_path)
    service.add_manual_candidate(symbol="1810.HK", name="小米集团", research_priority="L3")
    service.transition("1810.HK", lifecycle_status="ANALYZING")

    candidate = service.record_analysis_result(
        "1810.HK",
        analysis_version="company-research-v1",
        thesis_hash="abc123",
        summary="汽车毛利和交付仍需后续季度验证",
        lifecycle_status="WAITING_TRIGGER",
        cooldown_until="2026-08-21T09:00:00+08:00",
    )

    assert candidate["lifecycle_status"] == "WAITING_TRIGGER"
    assert candidate["analysis_version"] == "company-research-v1"
    assert candidate["thesis_hash"] == "abc123"
    assert candidate["cooldown_until"] == "2026-08-21T09:00:00+08:00"
    assert candidate["last_deep_analysis_at"]


def test_candidate_http_api_does_not_expose_trade_action_endpoint(tmp_path):
    service = _service(tmp_path)
    app = FastAPI()
    app.include_router(create_candidate_router(service))
    client = TestClient(app)

    created = client.post(
        "/v1/candidates",
        json={
            "symbol": "1810.HK",
            "name": "小米集团",
            "research_priority": "L3",
            "reason": "人工重点研究",
        },
    )
    assert created.status_code == 200
    assert created.json()["formal_trade_authority"] is False

    listed = client.get("/v1/candidates")
    assert listed.status_code == 200
    assert [item["symbol"] for item in listed.json()] == ["1810.HK"]

    paths = {route.path for route in app.routes}
    assert "/v1/candidates/{symbol}/open" not in paths
    assert "/v1/candidates/{symbol}/trade" not in paths
