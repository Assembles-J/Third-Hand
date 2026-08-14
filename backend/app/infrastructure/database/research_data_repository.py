"""SQLite persistence for Research Local-First snapshots."""
from __future__ import annotations

from datetime import datetime
import json
from uuid import uuid4

from app.domain.research.data_gateway import ResearchDataSnapshot, canonical_hash, canonical_json


class ResearchDataRepository:
    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS research_data_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    data_type TEXT NOT NULL,
                    symbol TEXT,
                    query_hash TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    source_reference TEXT,
                    as_of TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    coverage_keys_json TEXT NOT NULL DEFAULT '[]',
                    freshness_status TEXT NOT NULL,
                    usage_scope TEXT NOT NULL DEFAULT 'RESEARCH_ONLY',
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_research_data_lookup "
                "ON research_data_snapshots(data_type,symbol,query_hash,schema_version,fetched_at DESC)"
            )
            connection.execute("""
                CREATE TABLE IF NOT EXISTS research_data_fetch_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    data_type TEXT NOT NULL,
                    symbol TEXT,
                    query_hash TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    provider TEXT,
                    status TEXT NOT NULL,
                    cache_status TEXT NOT NULL,
                    remote_call_count INTEGER NOT NULL,
                    missing_coverage_json TEXT NOT NULL DEFAULT '[]',
                    snapshot_id TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_research_fetch_attempt_lookup "
                "ON research_data_fetch_attempts(data_type,symbol,started_at DESC)"
            )

    @staticmethod
    def _row_snapshot(row) -> ResearchDataSnapshot:
        return ResearchDataSnapshot(
            snapshot_id=str(row["snapshot_id"]),
            data_type=str(row["data_type"]),
            symbol=str(row["symbol"]) if row["symbol"] is not None else None,
            query_hash=str(row["query_hash"]),
            schema_version=str(row["schema_version"]),
            payload=json.loads(str(row["payload_json"])),
            payload_hash=str(row["payload_hash"]),
            provider=str(row["provider"]),
            source_reference=str(row["source_reference"]) if row["source_reference"] is not None else None,
            as_of=str(row["as_of"]),
            available_at=str(row["available_at"]),
            fetched_at=str(row["fetched_at"]),
            expires_at=str(row["expires_at"]),
            coverage_keys=tuple(json.loads(str(row["coverage_keys_json"] or "[]"))),
            freshness_status=str(row["freshness_status"]),
            usage_scope=str(row["usage_scope"]),
        )

    def latest(self, *, data_type: str, symbol: str | None, query_hash: str, schema_version: str) -> ResearchDataSnapshot | None:
        with self.store._connect() as connection:
            row = connection.execute(
                """SELECT * FROM research_data_snapshots
                   WHERE data_type=? AND symbol IS ? AND query_hash=? AND schema_version=?
                   ORDER BY fetched_at DESC, created_at DESC LIMIT 1""",
                (data_type, symbol, query_hash, schema_version),
            ).fetchone()
        return self._row_snapshot(row) if row else None

    def save_snapshot(
        self,
        *,
        data_type: str,
        symbol: str | None,
        query_hash: str,
        schema_version: str,
        payload: object,
        provider: str,
        source_reference: str | None,
        as_of: str,
        available_at: str,
        fetched_at: str,
        expires_at: str,
        coverage_keys: tuple[str, ...],
        freshness_status: str = "fresh",
    ) -> str:
        snapshot_id = str(uuid4())
        payload_json = canonical_json(payload)
        payload_hash = canonical_hash(payload)
        created_at = fetched_at
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO research_data_snapshots(
                    snapshot_id,data_type,symbol,query_hash,schema_version,payload_json,payload_hash,
                    provider,source_reference,as_of,available_at,fetched_at,expires_at,
                    coverage_keys_json,freshness_status,usage_scope,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snapshot_id,data_type,symbol,query_hash,schema_version,payload_json,payload_hash,
                    provider,source_reference,as_of,available_at,fetched_at,expires_at,
                    json.dumps(list(coverage_keys), ensure_ascii=False),freshness_status,"RESEARCH_ONLY",created_at,
                ),
            )
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> ResearchDataSnapshot | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_data_snapshots WHERE snapshot_id=?",
                (str(snapshot_id),),
            ).fetchone()
        return self._row_snapshot(row) if row else None

    def record_attempt(
        self,
        *,
        data_type: str,
        symbol: str | None,
        query_hash: str,
        schema_version: str,
        provider: str | None,
        status: str,
        cache_status: str,
        remote_call_count: int,
        missing_coverage: tuple[str, ...],
        snapshot_id: str | None,
        error: Exception | None,
        detail: dict[str, object],
        started_at: str,
        finished_at: str,
    ) -> None:
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO research_data_fetch_attempts(
                    attempt_id,data_type,symbol,query_hash,schema_version,provider,status,cache_status,
                    remote_call_count,missing_coverage_json,snapshot_id,error_type,error_message,
                    detail_json,started_at,finished_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),data_type,symbol,query_hash,schema_version,provider,status,cache_status,
                    int(remote_call_count),json.dumps(list(missing_coverage), ensure_ascii=False),snapshot_id,
                    type(error).__name__ if error else None,str(error) if error else None,
                    json.dumps(detail, ensure_ascii=False, sort_keys=True, default=str),started_at,finished_at,
                ),
            )
