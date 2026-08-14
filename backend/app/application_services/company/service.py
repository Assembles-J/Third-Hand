"""Company Intelligence context assembly.

The service consumes ResearchDataGateway snapshots and never imports a provider
SDK directly.  Research priority controls depth/cost, while every dataset remains
RESEARCH_ONLY and cannot become ActionPolicy input simply by appearing here.
"""
from __future__ import annotations

from app.domain.company.context import (
    CompanyContext,
    CompanyDatasetRef,
    analysis_depth_for_priority,
    required_dataset_specs,
)
from app.domain.research.data_gateway import ResearchDataRequest
from app.time_utils import beijing_now


class CompanyIntelligenceService:
    def __init__(
        self,
        *,
        gateway,
        repository,
        candidate_repository=None,
        provider_registry=None,
    ) -> None:
        self.gateway = gateway
        self.repository = repository
        self.candidate_repository = candidate_repository
        self.provider_registry = provider_registry

    @staticmethod
    def _symbol(value: str) -> str:
        symbol = str(value or "").strip().upper()
        if not symbol:
            raise ValueError("company symbol must not be blank")
        return symbol

    def _candidate(self, symbol: str) -> dict[str, object] | None:
        if self.candidate_repository is None:
            return None
        return self.candidate_repository.get(symbol)

    def _priority(self, symbol: str, explicit: str | None) -> str:
        if explicit:
            priority = str(explicit).strip().upper()
        else:
            candidate = self._candidate(symbol)
            priority = str((candidate or {}).get("research_priority") or "L1").upper()
        if priority not in {"L0", "L1", "L2", "L3", "L4"}:
            raise ValueError(f"unsupported research priority: {priority}")
        return priority

    def requirements(self, symbol: str, *, research_priority: str | None = None) -> dict[str, object]:
        symbol = self._symbol(symbol)
        priority = self._priority(symbol, research_priority)
        candidate = self._candidate(symbol)
        specs = required_dataset_specs(priority)
        registered = set(self.provider_registry.registered_data_types()) if self.provider_registry else set()
        items = []
        for spec in specs:
            request = ResearchDataRequest(
                data_type=spec.data_type,
                symbol=symbol,
                params={"dataset_key": spec.key},
                schema_version=spec.schema_version,
                max_age_seconds=spec.max_age_seconds,
            )
            local = self.gateway.get_local(request, allow_stale=True)
            items.append({
                "dataset_key": spec.key,
                "data_type": spec.data_type,
                "description": spec.description,
                "local_status": local.cache_status if local else "LOCAL_MISS",
                "snapshot_id": local.snapshot.snapshot_id if local else None,
                "freshness_status": local.snapshot.freshness_status if local else "missing",
                "provider_registered": spec.data_type in registered,
            })
        return {
            "symbol": symbol,
            "name": str((candidate or {}).get("name") or symbol),
            "research_priority": priority,
            "analysis_depth": analysis_depth_for_priority(priority),
            "required_datasets": items,
            "formal_trade_authority": False,
        }

    def build_context(
        self,
        symbol: str,
        *,
        research_priority: str | None = None,
        allow_remote: bool = True,
    ) -> dict[str, object]:
        symbol = self._symbol(symbol)
        candidate = self._candidate(symbol)
        priority = self._priority(symbol, research_priority)
        name = str((candidate or {}).get("name") or symbol)
        datasets: dict[str, object] = {}
        refs: list[CompanyDatasetRef] = []
        missing: list[str] = []
        stale: list[str] = []

        for spec in required_dataset_specs(priority):
            request = ResearchDataRequest(
                data_type=spec.data_type,
                symbol=symbol,
                params={"dataset_key": spec.key},
                schema_version=spec.schema_version,
                max_age_seconds=spec.max_age_seconds,
                allow_stale_on_error=True,
            )
            fetcher = self.provider_registry.get(spec.data_type) if self.provider_registry else None
            if allow_remote and fetcher is not None:
                result = self.gateway.get_or_fetch(request, fetcher=fetcher)
            else:
                result = self.gateway.get_local(request, allow_stale=True)

            if result is None:
                missing.append(spec.key)
                continue

            snapshot = result.snapshot
            datasets[spec.key] = snapshot.payload
            if snapshot.freshness_status != "fresh":
                stale.append(spec.key)
            refs.append(CompanyDatasetRef(
                dataset_key=spec.key,
                data_type=spec.data_type,
                snapshot_id=snapshot.snapshot_id,
                payload_hash=snapshot.payload_hash,
                provider=snapshot.provider,
                as_of=snapshot.as_of,
                available_at=snapshot.available_at,
                freshness_status=snapshot.freshness_status,
                coverage_keys=snapshot.coverage_keys,
            ))

        context = CompanyContext(
            symbol=symbol,
            name=name,
            research_priority=priority,
            analysis_depth=analysis_depth_for_priority(priority),
            generated_at=beijing_now().isoformat(),
            datasets=datasets,
            dataset_refs=tuple(refs),
            missing_datasets=tuple(missing),
            stale_datasets=tuple(stale),
        )
        payload = context.as_dict()
        saved = self.repository.save_context(payload)

        identity = datasets.get("identity_business_model")
        identity_ref = next((item for item in refs if item.dataset_key == "identity_business_model"), None)
        if isinstance(identity, dict):
            self.repository.upsert_profile(
                symbol=symbol,
                name=name,
                research_priority=priority,
                profile=identity,
                source_snapshot_id=identity_ref.snapshot_id if identity_ref else None,
            )
        return saved

    def latest_context(self, symbol: str) -> dict[str, object]:
        result = self.repository.latest_context(self._symbol(symbol))
        if not result:
            raise KeyError(symbol)
        return result
