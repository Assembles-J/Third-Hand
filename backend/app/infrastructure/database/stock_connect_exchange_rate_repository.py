"""Append-only persistence for official Stock Connect exchange-rate observations.

This adapter intentionally reuses the existing P1 ``raw_data_snapshots`` lineage
store.  It is not a generic FX cache, does not create a foreign-currency cash
balance, and does not infer any conversion rate.  Each changed SSE observation
becomes a new immutable snapshot and may supersede an earlier observation for
the same applicable date.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping


SCHEMA_VERSION = "STOCK_CONNECT_EXCHANGE_RATE_V1"
SOURCE_PREFIX = "SSE_STOCK_CONNECT"


def _canonical_payload(payload: Mapping[str, object]) -> tuple[str, str]:
    text = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


class StockConnectExchangeRateRepository:
    def __init__(self, store) -> None:
        self.store = store

    @staticmethod
    def _source_key(kind: str) -> str:
        normalized = str(kind or "").strip().upper()
        if normalized not in {"REFERENCE", "SETTLEMENT"}:
            raise ValueError("stock_connect_exchange_rate_kind_invalid")
        return f"{SOURCE_PREFIX}_{normalized}_RATE"

    @staticmethod
    def _data_class(kind: str) -> str:
        return f"STOCK_CONNECT_{str(kind).strip().upper()}_EXCHANGE_RATE"

    def save(self, observation: Mapping[str, object]) -> str:
        kind = str(observation.get("kind") or "").strip().upper()
        source_key = self._source_key(kind)
        applicable_date = str(observation.get("applicable_date") or "").strip()
        retrieved_at = str(observation.get("retrieved_at") or "").strip()
        if not applicable_date or not retrieved_at:
            raise ValueError("stock_connect_exchange_rate_observation_incomplete")

        payload = {
            **dict(observation),
            "schema_version": SCHEMA_VERSION,
            "kind": kind,
        }
        payload_json, payload_hash = _canonical_payload(payload)
        effective_at = f"{applicable_date}T00:00:00+08:00"
        snapshot_id = f"scfx:{kind.lower()}:{applicable_date}:{payload_hash[:20]}"

        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO data_source_registry(source_key,provider,data_class,retention_days,revision_policy,enabled,updated_at) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET "
                "provider=excluded.provider,data_class=excluded.data_class,retention_days=excluded.retention_days," 
                "revision_policy=excluded.revision_policy,enabled=excluded.enabled,updated_at=excluded.updated_at",
                (
                    source_key,
                    "AKShare/SSE",
                    self._data_class(kind),
                    3650,
                    "APPEND_ONLY_SOURCE_REVISION",
                    1,
                    retrieved_at,
                ),
            )
            previous = connection.execute(
                "SELECT snapshot_id,payload_hash FROM raw_data_snapshots "
                "WHERE source_key=? AND effective_at=? ORDER BY retrieved_at DESC, created_at DESC LIMIT 1",
                (source_key, effective_at),
            ).fetchone()
            if previous is not None and str(previous["payload_hash"]) == payload_hash:
                return str(previous["snapshot_id"])

            connection.execute(
                "INSERT OR IGNORE INTO raw_data_snapshots(" 
                "snapshot_id,source_key,symbol,data_class,effective_at,available_at,retrieved_at," 
                "payload_hash,payload,supersedes_snapshot_id,created_at" 
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    snapshot_id,
                    source_key,
                    None,
                    self._data_class(kind),
                    effective_at,
                    retrieved_at,
                    retrieved_at,
                    payload_hash,
                    payload_json,
                    str(previous["snapshot_id"]) if previous is not None else None,
                    retrieved_at,
                ),
            )
        return snapshot_id

    def latest(self, kind: str, *, applicable_date: str | None = None) -> dict[str, object] | None:
        source_key = self._source_key(kind)
        query = (
            "SELECT * FROM raw_data_snapshots WHERE source_key=? "
            "AND data_class=?"
        )
        params: list[object] = [source_key, self._data_class(kind)]
        if applicable_date is not None:
            query += " AND substr(effective_at,1,10)=?"
            params.append(str(applicable_date))
        query += " ORDER BY effective_at DESC,retrieved_at DESC,created_at DESC LIMIT 1"
        with self.store._connect() as connection:
            row = connection.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload"]))
        return {
            **payload,
            "snapshot_id": str(row["snapshot_id"]),
            "payload_hash": str(row["payload_hash"]),
            "supersedes_snapshot_id": (
                str(row["supersedes_snapshot_id"]) if row["supersedes_snapshot_id"] is not None else None
            ),
        }


__all__ = ["SCHEMA_VERSION", "StockConnectExchangeRateRepository"]
