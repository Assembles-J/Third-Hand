"""Local-First orchestration for AI / Research data.

Provider fetchers are called only when local data is stale/incompatible or lacks
required coverage.  A provider result is persisted and reread before it is
returned to callers, so raw remote objects never become AI context directly.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Callable

from app.domain.research.data_gateway import (
    ProviderFetchResult,
    ResearchDataRequest,
    ResearchDataResult,
    ResearchDataSnapshot,
)
from app.time_utils import beijing_now


ResearchFetcher = Callable[
    [ResearchDataRequest, tuple[str, ...], ResearchDataSnapshot | None],
    ProviderFetchResult,
]


class ResearchDataGateway:
    def __init__(self, repository) -> None:
        self.repository = repository

    @staticmethod
    def _parse(value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("snapshot timestamp must include timezone offset")
        return parsed

    @staticmethod
    def _missing_coverage(request: ResearchDataRequest, snapshot: ResearchDataSnapshot | None) -> tuple[str, ...]:
        existing = set(snapshot.coverage_keys if snapshot else ())
        return tuple(key for key in request.required_coverage_keys if key not in existing)

    def _fresh(self, request: ResearchDataRequest, snapshot: ResearchDataSnapshot | None, *, now: datetime) -> bool:
        if snapshot is None:
            return False
        if snapshot.schema_version != request.schema_version:
            return False
        if snapshot.usage_scope != "RESEARCH_ONLY":
            # This gateway never silently consumes or emits promoted POLICY data.
            return False
        if self._missing_coverage(request, snapshot):
            return False
        # expires_at is the persisted TTL boundary.  max_age_seconds also lets a
        # caller demand a stricter freshness budget than the snapshot's original
        # consumer without changing query identity.
        if self._parse(snapshot.expires_at) <= now:
            return False
        fetched_at = self._parse(snapshot.fetched_at)
        if request.max_age_seconds == 0:
            return False
        return (now - fetched_at).total_seconds() <= request.max_age_seconds

    def get_or_fetch(
        self,
        request: ResearchDataRequest,
        *,
        fetcher: ResearchFetcher,
    ) -> ResearchDataResult:
        started = beijing_now()
        existing = self.repository.latest(
            data_type=request.data_type,
            symbol=request.symbol,
            query_hash=request.query_hash,
            schema_version=request.schema_version,
        )
        missing = self._missing_coverage(request, existing)

        if self._fresh(request, existing, now=started):
            finished = beijing_now()
            self.repository.record_attempt(
                data_type=request.data_type,
                symbol=request.symbol,
                query_hash=request.query_hash,
                schema_version=request.schema_version,
                provider=existing.provider,
                status="ok",
                cache_status="LOCAL_FRESH_HIT",
                remote_call_count=0,
                missing_coverage=(),
                snapshot_id=existing.snapshot_id,
                error=None,
                detail={"local_first": True, "remote_skipped": True},
                started_at=started.isoformat(),
                finished_at=finished.isoformat(),
            )
            return ResearchDataResult(
                snapshot=existing,
                cache_status="LOCAL_FRESH_HIT",
                remote_call_count=0,
            )

        cache_status = "LOCAL_MISS" if existing is None else "LOCAL_STALE_OR_INCOMPLETE"
        try:
            # Fetcher receives only the coverage delta plus the previous persisted
            # snapshot. It must normalize/merge the fetched subset before returning
            # ProviderFetchResult. No raw DataFrame/response object may cross this
            # boundary because ProviderFetchResult validates JSON serializability.
            fetched = fetcher(request, missing, existing)
            fetched_at = beijing_now()
            expires_at = fetched_at + timedelta(seconds=max(0, request.max_age_seconds))
            coverage = tuple(dict.fromkeys((*(existing.coverage_keys if existing else ()), *fetched.coverage_keys)))
            snapshot_id = self.repository.save_snapshot(
                data_type=request.data_type,
                symbol=request.symbol,
                query_hash=request.query_hash,
                schema_version=request.schema_version,
                payload=fetched.payload,
                provider=fetched.provider,
                source_reference=fetched.source_reference,
                as_of=fetched.as_of,
                available_at=fetched.available_at,
                fetched_at=fetched_at.isoformat(),
                expires_at=expires_at.isoformat(),
                coverage_keys=coverage,
                freshness_status="fresh",
            )
            # Critical Local-First invariant: AI callers receive the persisted
            # representation, never the transient provider object.
            persisted = self.repository.get_snapshot(snapshot_id)
            if persisted is None:
                raise RuntimeError("research snapshot persistence failed")

            remaining = self._missing_coverage(request, persisted)
            if remaining:
                raise ValueError(f"research coverage still incomplete: {remaining}")

            finished = beijing_now()
            self.repository.record_attempt(
                data_type=request.data_type,
                symbol=request.symbol,
                query_hash=request.query_hash,
                schema_version=request.schema_version,
                provider=fetched.provider,
                status="ok",
                cache_status="REMOTE_REFRESH_PERSISTED",
                remote_call_count=1,
                missing_coverage=missing,
                snapshot_id=persisted.snapshot_id,
                error=None,
                detail={
                    "local_first": True,
                    "persist_before_return": True,
                    "source_reference": fetched.source_reference,
                    "provider_detail": dict(fetched.detail),
                },
                started_at=started.isoformat(),
                finished_at=finished.isoformat(),
            )
            return ResearchDataResult(
                snapshot=persisted,
                cache_status="REMOTE_REFRESH_PERSISTED",
                remote_call_count=1,
                missing_coverage_keys=missing,
            )
        except Exception as error:
            finished = beijing_now()
            fallback = existing if request.allow_stale_on_error else None
            self.repository.record_attempt(
                data_type=request.data_type,
                symbol=request.symbol,
                query_hash=request.query_hash,
                schema_version=request.schema_version,
                provider=None,
                status="degraded" if fallback else "error",
                cache_status="STALE_LOCAL_FALLBACK" if fallback else cache_status,
                remote_call_count=1,
                missing_coverage=missing,
                snapshot_id=fallback.snapshot_id if fallback else None,
                error=error,
                detail={"local_first": True, "stale_local_returned": bool(fallback)},
                started_at=started.isoformat(),
                finished_at=finished.isoformat(),
            )
            if fallback is not None:
                return ResearchDataResult(
                    snapshot=replace(fallback, freshness_status="stale"),
                    cache_status="STALE_LOCAL_FALLBACK",
                    remote_call_count=1,
                    missing_coverage_keys=missing,
                    provider_error=f"{type(error).__name__}: {error}",
                )
            raise
