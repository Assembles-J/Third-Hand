from __future__ import annotations

import pytest

from app.application_services.research.akshare_gateway import AkshareGatewayFetcher
from app.application_services.research.data_gateway import ResearchDataGateway
from app.domain.research.data_gateway import ResearchDataRequest
from app.infrastructure.database.research_data_repository import ResearchDataRepository
from app.infrastructure.providers.akshare_registry import (
    AkshareExecutionPolicy,
    AkshareRegistryService,
    AkshareResearchExecutor,
)
from app.storage import PortfolioStore


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient=None):
        assert orient == "records"
        return self.rows


class FakeAkshare:
    def __init__(self):
        self.calls = []

    def search(self, query):
        return FakeFrame([
            {"interface_name": "company_demo", "description": f"match:{query}"},
            {"interface_name": "other_demo", "description": "other"},
        ])

    def interface_info(self, name):
        return {"name": name, "parameters": ["symbol"]}

    def list_categories(self):
        return ["stock", "fund"]

    def company_demo(self, symbol):
        self.calls.append(symbol)
        return FakeFrame([
            {"symbol": symbol, "segment": "smartphone", "value": 1},
            {"symbol": symbol, "segment": "smart_ev", "value": 2},
        ])


def test_registry_discovery_does_not_grant_execution_authority():
    ak = FakeAkshare()
    registry = AkshareRegistryService(ak)
    policy = AkshareExecutionPolicy()

    results = registry.search("company")

    assert results[0]["interface_name"] == "company_demo"
    assert policy.is_allowed("company_demo") is False
    with pytest.raises(PermissionError):
        policy.require_allowed("company_demo")


def test_allowlisted_interface_executes_with_normalized_bounded_output():
    ak = FakeAkshare()
    executor = AkshareResearchExecutor(
        policy=AkshareExecutionPolicy(["company_demo"]),
        ak_module=ak,
        max_rows=1,
    )

    result = executor.execute("company_demo", {"symbol": "1810.HK"})

    assert ak.calls == ["1810.HK"]
    assert result["usage_scope"] == "RESEARCH_ONLY"
    assert result["truncated"] is True
    assert len(result["rows"]) == 1
    assert result["rows"][0]["segment"] == "smartphone"


def test_invalid_or_unallowlisted_interface_is_rejected_before_getattr():
    ak = FakeAkshare()
    executor = AkshareResearchExecutor(
        policy=AkshareExecutionPolicy(["company_demo"]),
        ak_module=ak,
    )

    with pytest.raises(ValueError, match="invalid AKShare interface name"):
        executor.execute("__dict__", {})
    with pytest.raises(PermissionError, match="not allowlisted"):
        executor.execute("other_demo", {})


def test_gateway_bridge_persists_dynamic_result_then_second_call_is_local(tmp_path):
    ak = FakeAkshare()
    executor = AkshareResearchExecutor(
        policy=AkshareExecutionPolicy(["company_demo"]),
        ak_module=ak,
    )
    fetcher = AkshareGatewayFetcher(
        executor=executor,
        interface_name="company_demo",
        argument_builder=lambda request, missing, previous: {"symbol": request.symbol},
    )
    gateway = ResearchDataGateway(ResearchDataRepository(PortfolioStore(tmp_path / "registry.db")))
    request = ResearchDataRequest(
        data_type="company_products_segments",
        symbol="1810.HK",
        params={"scope": "segments"},
        schema_version="company-segments-v1",
        max_age_seconds=3600,
    )

    first = gateway.get_or_fetch(request, fetcher=fetcher)
    second = gateway.get_or_fetch(request, fetcher=fetcher)

    assert first.cache_status == "REMOTE_REFRESH_PERSISTED"
    assert first.snapshot.provider == "akshare_registry"
    assert first.snapshot.usage_scope == "RESEARCH_ONLY"
    assert first.snapshot.payload["interface_name"] == "company_demo"
    assert second.cache_status == "LOCAL_FRESH_HIT"
    assert second.remote_call_count == 0
    assert ak.calls == ["1810.HK"]
