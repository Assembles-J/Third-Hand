from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.research.company_router import create_company_intelligence_router
from app.application_services.candidate.service import CandidateService
from app.application_services.company.provider_registry import CompanyDataProviderRegistry
from app.application_services.company.service import CompanyIntelligenceService
from app.application_services.research.data_gateway import ResearchDataGateway
from app.domain.company.context import required_dataset_specs
from app.domain.research.data_gateway import ProviderFetchResult
from app.infrastructure.database.candidate_repository import CandidateRepository
from app.infrastructure.database.company_intelligence_repository import CompanyIntelligenceRepository
from app.infrastructure.database.research_data_repository import ResearchDataRepository
from app.storage import PortfolioStore


def _stack(tmp_path):
    store = PortfolioStore(tmp_path / "company-intelligence.db")
    candidate_repo = CandidateRepository(store)
    candidate_service = CandidateService(candidate_repo)
    gateway = ResearchDataGateway(ResearchDataRepository(store))
    providers = CompanyDataProviderRegistry()
    service = CompanyIntelligenceService(
        gateway=gateway,
        repository=CompanyIntelligenceRepository(store),
        candidate_repository=candidate_repo,
        provider_registry=providers,
    )
    return candidate_service, providers, service


def _payload_for(data_type: str):
    if data_type == "company_identity_business_model":
        return {
            "business_model": "智能手机 + IoT + 互联网服务 + 智能汽车",
            "products": ["smartphone", "iot", "internet_services", "smart_ev"],
        }
    if data_type == "company_products_segments":
        return {
            "segments": {
                "smartphone": {"role": "scale_and_ecosystem"},
                "iot": {"role": "ecosystem_expansion"},
                "internet_services": {"role": "high_margin_monetization"},
                "smart_ev": {"role": "new_growth_engine"},
            }
        }
    if data_type == "company_margin_structure":
        return {"gross_margin": {"group": 0.22, "smart_ev": 0.18}, "as_reported": True}
    return {"dataset": data_type, "facts": [{"source": "test", "value": 1}]}


def test_l3_company_context_is_deep_local_first_and_reuses_persisted_snapshots(tmp_path):
    candidate_service, providers, service = _stack(tmp_path)
    candidate_service.add_manual_candidate(
        symbol="1810.HK",
        name="小米集团",
        research_priority="L3",
        reason="深度研究产品线、利润与汽车业务",
    )
    calls: dict[str, int] = {}
    for spec in required_dataset_specs("L3"):
        def fetcher(request, missing, previous, *, key=spec.data_type):
            calls[key] = calls.get(key, 0) + 1
            return ProviderFetchResult(
                provider=f"test:{key}",
                payload=_payload_for(key),
                as_of="2026-08-14T18:00:00+08:00",
                available_at="2026-08-14T18:01:00+08:00",
                source_reference=f"test://{key}",
                detail={"normalized": True},
            )
        providers.register(spec.data_type, fetcher)

    first = service.build_context("1810.HK")
    calls_after_first = sum(calls.values())
    second = service.build_context("1810.HK")

    assert first["research_priority"] == "L3"
    assert first["analysis_depth"] == "deep_company"
    assert first["research_ready"] is True
    assert first["formal_trade_authority"] is False
    assert first["missing_datasets"] == []
    assert set(first["datasets"]) == {spec.key for spec in required_dataset_specs("L3")}
    assert first["datasets"]["identity_business_model"]["products"][-1] == "smart_ev"
    assert "internet_services" in first["datasets"]["products_segments"]["segments"]
    assert first["datasets"]["margin_structure"]["gross_margin"]["smart_ev"] == 0.18
    assert calls_after_first == len(required_dataset_specs("L3"))
    assert sum(calls.values()) == calls_after_first, "second build must reuse fresh local snapshots"
    assert second["context_id"] != first["context_id"]
    assert all(ref["snapshot_id"] for ref in second["dataset_refs"])


def test_missing_provider_or_local_data_is_explicit_not_ai_invented(tmp_path):
    candidate_service, providers, service = _stack(tmp_path)
    candidate_service.add_manual_candidate(symbol="1810.HK", name="小米集团", research_priority="L3")

    context = service.build_context("1810.HK", allow_remote=True)

    assert context["research_ready"] is False
    assert context["formal_trade_authority"] is False
    assert set(context["missing_datasets"]) == {spec.key for spec in required_dataset_specs("L3")}
    assert context["datasets"] == {}


def test_research_priority_controls_required_company_depth(tmp_path):
    _, _, service = _stack(tmp_path)

    l1 = service.requirements("600519", research_priority="L1")
    l3 = service.requirements("600519", research_priority="L3")

    assert l1["analysis_depth"] == "basic_company"
    assert l3["analysis_depth"] == "deep_company"
    assert len(l1["required_datasets"]) < len(l3["required_datasets"])
    assert {item["dataset_key"] for item in l1["required_datasets"]} == {
        "identity_business_model", "products_segments",
    }
    assert "margin_structure" in {item["dataset_key"] for item in l3["required_datasets"]}
    assert "industry_competition" in {item["dataset_key"] for item in l3["required_datasets"]}


def test_company_api_exposes_research_context_but_no_trade_endpoint(tmp_path):
    _, _, service = _stack(tmp_path)
    app = FastAPI()
    app.include_router(create_company_intelligence_router(service))
    client = TestClient(app)

    response = client.post(
        "/v1/company-intelligence/1810.HK/build",
        json={"research_priority": "L1", "allow_remote": False},
    )
    assert response.status_code == 200
    assert response.json()["formal_trade_authority"] is False

    paths = {path for route in app.routes if (path := getattr(route, "path", None))}
    assert "/v1/company-intelligence/{symbol}/open" not in paths
    assert "/v1/company-intelligence/{symbol}/trade" not in paths
