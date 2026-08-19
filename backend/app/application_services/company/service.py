"""Company Intelligence context assembly.

Research priority controls depth/cost. Every dataset comes from the persisted
ResearchDataGateway plane and remains RESEARCH_ONLY; appearing in CompanyContext
does not make it an ActionPolicy input.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import logging

from app.domain.company.context import (
    CompanyContext,
    CompanyDatasetRef,
    analysis_depth_for_priority,
    required_dataset_specs,
)
from app.domain.research.data_gateway import ResearchDataRequest, ResearchDataResult
from app.time_utils import beijing_now


logger = logging.getLogger(__name__)


class CompanyIntelligenceService:
    def __init__(self, *, gateway, repository, candidate_repository=None, provider_registry=None) -> None:
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

    @staticmethod
    def _parse(value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("company research timestamp must include timezone offset")
        return parsed

    def _candidate(self, symbol: str) -> dict[str, object] | None:
        return self.candidate_repository.get(symbol) if self.candidate_repository is not None else None

    def _priority(self, symbol: str, explicit: str | None) -> str:
        candidate = self._candidate(symbol)
        priority = str(explicit or (candidate or {}).get("research_priority") or "L1").strip().upper()
        if priority not in {"L0", "L1", "L2", "L3", "L4"}:
            raise ValueError(f"unsupported research priority: {priority}")
        return priority

    def _provider_supported(self, data_type: str, symbol: str) -> bool:
        if self.provider_registry is None:
            return False
        supports = getattr(self.provider_registry, "supports", None)
        if callable(supports):
            return bool(supports(data_type, symbol))
        return self.provider_registry.get(data_type) is not None

    def _local_only(self, request: ResearchDataRequest) -> ResearchDataResult | None:
        """Read persisted research data without ever invoking a provider."""
        now = beijing_now()
        snapshot = self.gateway.repository.latest(
            data_type=request.data_type,
            symbol=request.symbol,
            query_hash=request.query_hash,
            schema_version=request.schema_version,
        )
        if snapshot is None:
            return None
        fresh = (
            snapshot.usage_scope == "RESEARCH_ONLY"
            and self._parse(snapshot.expires_at) > now
            and request.max_age_seconds > 0
            and (now - self._parse(snapshot.fetched_at)).total_seconds() <= request.max_age_seconds
        )
        resolved = snapshot if fresh else replace(snapshot, freshness_status="stale")
        self.gateway.repository.record_attempt(
            data_type=request.data_type,
            symbol=request.symbol,
            query_hash=request.query_hash,
            schema_version=request.schema_version,
            provider=snapshot.provider,
            status="ok" if fresh else "degraded",
            cache_status="LOCAL_FRESH_HIT" if fresh else "LOCAL_STALE_HIT",
            remote_call_count=0,
            missing_coverage=(),
            snapshot_id=snapshot.snapshot_id,
            error=None,
            detail={"company_context_local_only": True},
            started_at=now.isoformat(),
            finished_at=beijing_now().isoformat(),
        )
        return ResearchDataResult(
            snapshot=resolved,
            cache_status="LOCAL_FRESH_HIT" if fresh else "LOCAL_STALE_HIT",
            remote_call_count=0,
        )

    def requirements(self, symbol: str, *, research_priority: str | None = None) -> dict[str, object]:
        symbol = self._symbol(symbol)
        priority = self._priority(symbol, research_priority)
        candidate = self._candidate(symbol)
        items = []
        for spec in required_dataset_specs(priority):
            request = ResearchDataRequest(
                data_type=spec.data_type,
                symbol=symbol,
                params={"dataset_key": spec.key},
                schema_version=spec.schema_version,
                max_age_seconds=spec.max_age_seconds,
            )
            local = self._local_only(request)
            items.append({
                "dataset_key": spec.key,
                "data_type": spec.data_type,
                "description": spec.description,
                "local_status": local.cache_status if local else "LOCAL_MISS",
                "snapshot_id": local.snapshot.snapshot_id if local else None,
                "freshness_status": local.snapshot.freshness_status if local else "missing",
                "provider_registered": self._provider_supported(spec.data_type, symbol),
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
        force_refresh_data_types: tuple[str, ...] = (),
        refresh_reason: str | None = None,
    ) -> dict[str, object]:
        symbol = self._symbol(symbol)
        candidate = self._candidate(symbol)
        priority = self._priority(symbol, research_priority)
        name = str((candidate or {}).get("name") or symbol)
        datasets: dict[str, object] = {}
        refs: list[CompanyDatasetRef] = []
        missing: list[str] = []
        stale: list[str] = []
        forced = {str(item).strip().lower() for item in force_refresh_data_types if str(item).strip()}

        for spec in required_dataset_specs(priority):
            request = ResearchDataRequest(
                data_type=spec.data_type,
                symbol=symbol,
                params={"dataset_key": spec.key},
                schema_version=spec.schema_version,
                max_age_seconds=spec.max_age_seconds,
                allow_stale_on_error=True,
            )
            supported = self._provider_supported(spec.data_type, symbol)
            fetcher = self.provider_registry.get(spec.data_type) if supported else None
            try:
                result = (
                    self.gateway.get_or_fetch(
                        request,
                        fetcher=fetcher,
                        force_refresh=spec.data_type in forced,
                        refresh_reason=refresh_reason if spec.data_type in forced else None,
                    )
                    if allow_remote and fetcher is not None
                    else self._local_only(request)
                )
            except Exception as error:
                # Company datasets are independent research enrichments. One
                # unavailable endpoint must not discard the datasets that are
                # available for the same company.
                logger.warning(
                    "company dataset unavailable symbol=%s dataset=%s error_type=%s",
                    symbol,
                    spec.key,
                    type(error).__name__,
                )
                result = self._local_only(request)
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
        return self.repository.save_context(context.as_dict())

    def latest_context(self, symbol: str) -> dict[str, object]:
        result = self.repository.latest_context(self._symbol(symbol))
        if not result:
            raise KeyError(symbol)
        return result
