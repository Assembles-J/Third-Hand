"""Pure contracts for the Research Local-First Data Gateway.

Remote providers are refresh/fill adapters, never the AI's default data plane.
Every successful remote result must be normalized and persisted before callers
receive it. All snapshots created by this gateway are RESEARCH_ONLY unless a
separate governance promotion process creates a formal POLICY feature.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping


USAGE_SCOPE = "RESEARCH_ONLY"


def canonical_json(value: object) -> str:
    """Canonical strict JSON used for research query/payload lineage.

    There is intentionally no ``default=str`` escape hatch: provider adapters
    must normalize DataFrame/Decimal/custom objects before crossing the gateway.
    This prevents accidental prompt injection of opaque raw provider objects.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchDataRequest:
    data_type: str
    symbol: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "research-data-v1"
    max_age_seconds: int = 86_400
    required_coverage_keys: tuple[str, ...] = ()
    allow_stale_on_error: bool = True

    def __post_init__(self) -> None:
        if not str(self.data_type or "").strip():
            raise ValueError("data_type must not be blank")
        if not str(self.schema_version or "").strip():
            raise ValueError("schema_version must not be blank")
        if int(self.max_age_seconds) < 0:
            raise ValueError("max_age_seconds must be >= 0")
        normalized_symbol = str(self.symbol or "").strip().upper() or None
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "data_type", str(self.data_type).strip().lower())
        object.__setattr__(self, "schema_version", str(self.schema_version).strip())
        object.__setattr__(
            self,
            "required_coverage_keys",
            tuple(dict.fromkeys(str(item).strip() for item in self.required_coverage_keys if str(item).strip())),
        )
        # Query identity must itself be serializable and auditable.
        canonical_json(dict(self.params))

    @property
    def query_hash(self) -> str:
        # TTL/allow-stale are consumption policy, not query identity. Coverage
        # keys are also excluded so a larger follow-up request can reuse the same
        # persisted dataset and fetch only missing coverage.
        return canonical_hash({
            "data_type": self.data_type,
            "symbol": self.symbol,
            "params": dict(self.params),
            "schema_version": self.schema_version,
        })


@dataclass(frozen=True)
class ProviderFetchResult:
    """Normalized provider output accepted by the gateway.

    Provider adapters must convert raw DataFrame/JSON into JSON-serializable
    payloads before constructing this object. The gateway then persists and
    rereads it; callers never receive this object directly as AI context.
    """

    provider: str
    payload: Any
    as_of: str
    available_at: str
    source_reference: str | None = None
    coverage_keys: tuple[str, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.provider or "").strip():
            raise ValueError("provider must not be blank")
        if not str(self.as_of or "").strip():
            raise ValueError("as_of must not be blank")
        if not str(self.available_at or "").strip():
            raise ValueError("available_at must not be blank")
        # Validate parseability early; timezone-naive values are allowed for
        # exchange/report dates, while exact timestamps should carry offsets.
        for value, label in ((self.as_of, "as_of"), (self.available_at, "available_at")):
            try:
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError(f"{label} must be ISO-8601 compatible") from error
        # Fails for unserializable raw provider objects/DataFrames.
        canonical_json(self.payload)
        canonical_json(dict(self.detail))
        object.__setattr__(
            self,
            "coverage_keys",
            tuple(dict.fromkeys(str(item).strip() for item in self.coverage_keys if str(item).strip())),
        )


@dataclass(frozen=True)
class ResearchDataSnapshot:
    snapshot_id: str
    data_type: str
    symbol: str | None
    query_hash: str
    schema_version: str
    payload: Any
    payload_hash: str
    provider: str
    source_reference: str | None
    as_of: str
    available_at: str
    fetched_at: str
    expires_at: str
    coverage_keys: tuple[str, ...]
    freshness_status: str
    usage_scope: str = USAGE_SCOPE


@dataclass(frozen=True)
class ResearchDataResult:
    snapshot: ResearchDataSnapshot
    cache_status: str
    remote_call_count: int
    missing_coverage_keys: tuple[str, ...] = ()
    provider_error: str | None = None

    @property
    def data_snapshot_id(self) -> str:
        return self.snapshot.snapshot_id

    @property
    def data_hash(self) -> str:
        return self.snapshot.payload_hash
