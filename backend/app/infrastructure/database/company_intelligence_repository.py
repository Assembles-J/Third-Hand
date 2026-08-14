"""SQLite persistence for assembled Company Intelligence contexts."""
from __future__ import annotations

import json
from uuid import uuid4

from app.domain.research.data_gateway import canonical_hash, canonical_json
from app.time_utils import beijing_now


class CompanyIntelligenceRepository:
    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS company_profiles (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    research_priority TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    source_snapshot_id TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS company_research_snapshots (
                    context_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    research_priority TEXT NOT NULL,
                    analysis_depth TEXT NOT NULL,
                    version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    usage_scope TEXT NOT NULL DEFAULT 'RESEARCH_ONLY',
                    formal_trade_authority INTEGER NOT NULL DEFAULT 0,
                    generated_at TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_company_research_symbol_time "
                "ON company_research_snapshots(symbol, generated_at DESC)"
            )

    def save_context(self, payload: dict[str, object]) -> dict[str, object]:
        context_id = str(uuid4())
        payload_json = canonical_json(payload)
        payload_hash = canonical_hash(payload)
        generated_at = str(payload["generated_at"])
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO company_research_snapshots(
                    context_id,symbol,name,research_priority,analysis_depth,version,
                    payload_json,payload_hash,usage_scope,formal_trade_authority,generated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    context_id,
                    str(payload["symbol"]),
                    str(payload["name"]),
                    str(payload["research_priority"]),
                    str(payload["analysis_depth"]),
                    str(payload["version"]),
                    payload_json,
                    payload_hash,
                    "RESEARCH_ONLY",
                    0,
                    generated_at,
                ),
            )
        return {**payload, "context_id": context_id, "payload_hash": payload_hash}

    def latest_context(self, symbol: str) -> dict[str, object] | None:
        with self.store._connect() as connection:
            row = connection.execute(
                """SELECT context_id,payload_json,payload_hash
                   FROM company_research_snapshots
                   WHERE symbol=? ORDER BY generated_at DESC LIMIT 1""",
                (str(symbol).strip().upper(),),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(str(row["payload_json"]))
        return {**payload, "context_id": str(row["context_id"]), "payload_hash": str(row["payload_hash"])}

    def upsert_profile(
        self,
        *,
        symbol: str,
        name: str,
        research_priority: str,
        profile: dict[str, object],
        source_snapshot_id: str | None,
    ) -> None:
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO company_profiles(symbol,name,research_priority,profile_json,source_snapshot_id,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(symbol) DO UPDATE SET
                     name=excluded.name,
                     research_priority=excluded.research_priority,
                     profile_json=excluded.profile_json,
                     source_snapshot_id=excluded.source_snapshot_id,
                     updated_at=excluded.updated_at""",
                (
                    str(symbol).strip().upper(),
                    str(name),
                    str(research_priority),
                    canonical_json(profile),
                    source_snapshot_id,
                    beijing_now().isoformat(),
                ),
            )
