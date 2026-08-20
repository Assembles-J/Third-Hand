"""Immutable experiment-universe membership for N3 evaluation.

The daily Personal Universe (positions/watchlist/discovery) is intentionally
mutable. Evaluation must never read that mutable set dynamically. Every
experiment version therefore binds to one frozen, deterministic universe
snapshot containing the exact market/symbol members eligible for that version.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
import hashlib
import json

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ExperimentUniverseSourceKind(str, Enum):
    EXPLICIT = "EXPLICIT"
    PERSONAL_UNIVERSE_FREEZE = "PERSONAL_UNIVERSE_FREEZE"
    REPLAY_FIXTURE = "REPLAY_FIXTURE"


class ExperimentUniverseMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    market: str

    @field_validator("symbol")
    @classmethod
    def _canonical_symbol(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if not normalized:
            raise ValueError("experiment universe symbol must not be blank")
        return normalized

    @field_validator("market")
    @classmethod
    def _canonical_market(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        aliases = {"CN_A": "CN", "A": "CN", "MAINLAND": "CN"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"CN", "HK", "US"}:
            raise ValueError("experiment universe market must be CN, HK, or US")
        return normalized


class ExperimentUniverseSnapshot(BaseModel):
    """Exact immutable membership for one experiment version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    universe_snapshot_id: str
    experiment_id: str
    experiment_version: str
    universe_policy_version: str
    captured_at: datetime
    members: tuple[ExperimentUniverseMember, ...]
    source_kind: ExperimentUniverseSourceKind = ExperimentUniverseSourceKind.EXPLICIT
    source_reference_hash: str | None = None

    @field_validator(
        "universe_snapshot_id",
        "experiment_id",
        "experiment_version",
        "universe_policy_version",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("experiment universe identity/version fields must not be blank")
        return normalized

    @field_validator("captured_at")
    @classmethod
    def _timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("experiment universe captured_at must include timezone information")
        return value

    @field_validator("source_reference_hash")
    @classmethod
    def _optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if not normalized:
            return None
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("source_reference_hash must be a sha256 hex digest")
        return normalized

    @field_validator("members", mode="before")
    @classmethod
    def _canonical_members(cls, value):
        raw = tuple(value or ())
        if not raw:
            raise ValueError("experiment universe requires at least one member")
        parsed = tuple(ExperimentUniverseMember.model_validate(item) for item in raw)
        keys = [(item.market, item.symbol) for item in parsed]
        if len(keys) != len(set(keys)):
            raise ValueError("experiment universe members must be unique by market/symbol")
        return tuple(sorted(parsed, key=lambda item: (item.market, item.symbol)))

    @model_validator(mode="after")
    def _membership_nonempty(self) -> "ExperimentUniverseSnapshot":
        if not self.members:
            raise ValueError("experiment universe requires at least one member")
        return self

    def contains(self, symbol: str, market: str) -> bool:
        candidate = ExperimentUniverseMember(symbol=symbol, market=market)
        return candidate in self.members

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude_none=False)

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def snapshot_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


__all__ = [
    "ExperimentUniverseMember",
    "ExperimentUniverseSnapshot",
    "ExperimentUniverseSourceKind",
]
