from __future__ import annotations

import pytest

from app.application_services.research.data_gateway import ResearchDataGateway
from app.domain.research.data_gateway import ProviderFetchResult, ResearchDataRequest
from app.infrastructure.database.research_data_repository import ResearchDataRepository
from app.storage import PortfolioStore


def _gateway(tmp_path) -> ResearchDataGateway:
    store = PortfolioStore(tmp_path / "research-gateway.db")
    return ResearchDataGateway(ResearchDataRepository(store))


def _result(payload, *, coverage=(), provider="test-provider") -> ProviderFetchResult:
    return ProviderFetchResult(
        provider=provider,
        payload=payload,
        as_of="2026-08-14T15:00:00+08:00",
        available_at="2026-08-14T15:01:00+08:00",
        source_reference="test://source",
        coverage_keys=tuple(coverage),
        detail={"normalized": True},
    )


def test_fresh_local_snapshot_skips_remote_provider_exactly_zero_calls(tmp_path):
    gateway = _gateway(tmp_path)
    request = ResearchDataRequest(
        data_type="company_profile",
        symbol="1810.HK",
        params={"scope": "business_segments"},
        max_age_seconds=3600,
        required_coverage_keys=("smartphone", "iot"),
    )
    calls = []

    def fetcher(req, missing, previous):
        calls.append((missing, previous))
        return _result(
            {"segments": {"smartphone": {}, "iot": {}}},
            coverage=("smartphone", "iot"),
        )

    first = gateway.get_or_fetch(request, fetcher=fetcher)
    second = gateway.get_or_fetch(request, fetcher=fetcher)

    assert first.remote_call_count == 1
    assert first.cache_status == "REMOTE_REFRESH_PERSISTED"
    assert second.remote_call_count == 0
    assert second.cache_status == "LOCAL_FRESH_HIT"
    assert second.data_snapshot_id == first.data_snapshot_id
    assert len(calls) == 1


def test_only_missing_coverage_is_requested_and_merged_result_is_persisted(tmp_path):
    gateway = _gateway(tmp_path)
    base = ResearchDataRequest(
        data_type="company_metrics",
        symbol="1810.HK",
        params={"period": "annual"},
        max_age_seconds=3600,
        required_coverage_keys=("2024", "2025"),
    )
    gateway.get_or_fetch(
        base,
        fetcher=lambda req, missing, previous: _result(
            {"metrics": {"2024": {"revenue": 1}, "2025": {"revenue": 2}}},
            coverage=missing,
        ),
    )

    expanded = ResearchDataRequest(
        data_type="company_metrics",
        symbol="1810.HK",
        params={"period": "annual"},
        max_age_seconds=3600,
        required_coverage_keys=("2024", "2025", "2026"),
    )
    seen = {}

    def fetch_missing(req, missing, previous):
        seen["missing"] = missing
        seen["previous"] = previous
        merged = dict(previous.payload["metrics"])
        merged["2026"] = {"revenue": 3}
        return _result({"metrics": merged}, coverage=missing)

    result = gateway.get_or_fetch(expanded, fetcher=fetch_missing)

    assert seen["missing"] == ("2026",)
    assert seen["previous"] is not None
    assert result.missing_coverage_keys == ("2026",)
    assert result.snapshot.coverage_keys == ("2024", "2025", "2026")
    assert result.snapshot.payload["metrics"]["2026"]["revenue"] == 3
    persisted = gateway.repository.get_snapshot(result.snapshot.snapshot_id)
    assert persisted is not None
    assert persisted.payload == result.snapshot.payload


def test_remote_failure_returns_explicit_stale_local_when_allowed(tmp_path):
    gateway = _gateway(tmp_path)
    warm = ResearchDataRequest(
        data_type="company_news",
        symbol="1810.HK",
        params={"window": "30d"},
        max_age_seconds=3600,
    )
    gateway.get_or_fetch(
        warm,
        fetcher=lambda req, missing, previous: _result({"news": [{"id": "n1"}]}),
    )

    force_refresh = ResearchDataRequest(
        data_type="company_news",
        symbol="1810.HK",
        params={"window": "30d"},
        max_age_seconds=0,
        allow_stale_on_error=True,
    )

    def fail(req, missing, previous):
        raise ConnectionError("provider unavailable")

    result = gateway.get_or_fetch(force_refresh, fetcher=fail)

    assert result.cache_status == "STALE_LOCAL_FALLBACK"
    assert result.remote_call_count == 1
    assert result.snapshot.freshness_status == "stale"
    assert "ConnectionError" in (result.provider_error or "")


def test_remote_failure_without_local_snapshot_raises(tmp_path):
    gateway = _gateway(tmp_path)
    request = ResearchDataRequest(data_type="financials", symbol="1810.HK")

    def fail(req, missing, previous):
        raise ConnectionError("provider unavailable")

    with pytest.raises(ConnectionError, match="provider unavailable"):
        gateway.get_or_fetch(request, fetcher=fail)


def test_raw_unserializable_provider_payload_is_rejected_before_persistence(tmp_path):
    gateway = _gateway(tmp_path)
    request = ResearchDataRequest(data_type="company_profile", symbol="1810.HK")

    def invalid_fetcher(req, missing, previous):
        return ProviderFetchResult(
            provider="bad-provider",
            payload={"raw": object()},
            as_of="2026-08-14",
            available_at="2026-08-14",
        )

    with pytest.raises(TypeError):
        gateway.get_or_fetch(request, fetcher=invalid_fetcher)

    assert gateway.repository.latest(
        data_type=request.data_type,
        symbol=request.symbol,
        query_hash=request.query_hash,
        schema_version=request.schema_version,
    ) is None


def test_query_identity_ignores_ttl_but_includes_schema_and_params():
    first = ResearchDataRequest(
        data_type="company_profile",
        symbol="1810.hk",
        params={"scope": "segments"},
        schema_version="company-profile-v1",
        max_age_seconds=60,
    )
    stricter = ResearchDataRequest(
        data_type="company_profile",
        symbol="1810.HK",
        params={"scope": "segments"},
        schema_version="company-profile-v1",
        max_age_seconds=1,
    )
    changed = ResearchDataRequest(
        data_type="company_profile",
        symbol="1810.HK",
        params={"scope": "segments-and-margins"},
        schema_version="company-profile-v1",
    )

    assert first.query_hash == stricter.query_hash
    assert first.query_hash != changed.query_hash
