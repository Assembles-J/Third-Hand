"""SQLite adapter for Candidate Management v1.3.

The repository owns new v2 candidate tables without adding more persistence code
to the legacy PortfolioStore monolith.  Existing PortfolioStore connection and
busy-timeout behavior are reused during the strangler migration.
"""
from __future__ import annotations

import json
from uuid import uuid4

from app.time_utils import beijing_now


class CandidateRepository:
    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS candidate_entries (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    research_priority TEXT NOT NULL,
                    lifecycle_status TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    last_deep_analysis_at TEXT,
                    analysis_version TEXT,
                    thesis_hash TEXT,
                    cooldown_until TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS candidate_sources (
                    symbol TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(symbol, source_type, source_key)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS candidate_activation_rules (
                    rule_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    usage_scope TEXT NOT NULL DEFAULT 'RESEARCH_ONLY',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_activation_symbol_enabled "
                "ON candidate_activation_rules(symbol, enabled, updated_at DESC)"
            )
            connection.execute("""
                CREATE TABLE IF NOT EXISTS candidate_events (
                    event_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_events_symbol_time "
                "ON candidate_events(symbol, created_at DESC)"
            )
            connection.execute("""
                CREATE TABLE IF NOT EXISTS candidate_analysis_runs (
                    run_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    status TEXT NOT NULL,
                    analysis_version TEXT,
                    thesis_hash TEXT,
                    summary TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_analysis_symbol_time "
                "ON candidate_analysis_runs(symbol, started_at DESC)"
            )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        value = str(symbol or "").strip().upper()
        if not value:
            raise ValueError("candidate symbol must not be blank")
        return value

    def upsert_entry(
        self,
        *,
        symbol: str,
        name: str,
        research_priority: str,
        lifecycle_status: str,
        reason: str,
    ) -> dict[str, object]:
        symbol = self._normalize_symbol(symbol)
        now = beijing_now().isoformat()
        with self.store._connect() as connection:
            existing = connection.execute(
                "SELECT created_at,last_deep_analysis_at,analysis_version,thesis_hash,cooldown_until FROM candidate_entries WHERE symbol=?",
                (symbol,),
            ).fetchone()
            created_at = str(existing["created_at"]) if existing else now
            connection.execute(
                """INSERT INTO candidate_entries(
                       symbol,name,research_priority,lifecycle_status,reason,
                       last_deep_analysis_at,analysis_version,thesis_hash,cooldown_until,
                       created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(symbol) DO UPDATE SET
                       name=excluded.name,
                       research_priority=excluded.research_priority,
                       lifecycle_status=excluded.lifecycle_status,
                       reason=excluded.reason,
                       updated_at=excluded.updated_at""",
                (
                    symbol,
                    str(name or symbol).strip() or symbol,
                    research_priority,
                    lifecycle_status,
                    str(reason or "").strip(),
                    existing["last_deep_analysis_at"] if existing else None,
                    existing["analysis_version"] if existing else None,
                    existing["thesis_hash"] if existing else None,
                    existing["cooldown_until"] if existing else None,
                    created_at,
                    now,
                ),
            )
        return self.get(symbol) or {}

    def add_source(self, *, symbol: str, source_type: str, source_key: str, reason: str = "") -> None:
        symbol = self._normalize_symbol(symbol)
        now = beijing_now().isoformat()
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO candidate_sources(symbol,source_type,source_key,reason,created_at,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(symbol,source_type,source_key) DO UPDATE SET
                     reason=excluded.reason, updated_at=excluded.updated_at""",
                (symbol, source_type, str(source_key or source_type), str(reason or ""), now, now),
            )

    def update_lifecycle(
        self,
        *,
        symbol: str,
        lifecycle_status: str,
        reason: str | None = None,
        cooldown_until: str | None = None,
    ) -> dict[str, object]:
        symbol = self._normalize_symbol(symbol)
        now = beijing_now().isoformat()
        with self.store._connect() as connection:
            current = connection.execute(
                "SELECT lifecycle_status,reason FROM candidate_entries WHERE symbol=?",
                (symbol,),
            ).fetchone()
            if not current:
                raise KeyError(symbol)
            connection.execute(
                """UPDATE candidate_entries
                   SET lifecycle_status=?, reason=?, cooldown_until=?, updated_at=?
                   WHERE symbol=?""",
                (
                    lifecycle_status,
                    str(reason) if reason is not None else str(current["reason"]),
                    cooldown_until,
                    now,
                    symbol,
                ),
            )
        return self.get(symbol) or {}

    def update_priority(self, *, symbol: str, research_priority: str) -> dict[str, object]:
        symbol = self._normalize_symbol(symbol)
        with self.store._connect() as connection:
            result = connection.execute(
                "UPDATE candidate_entries SET research_priority=?,updated_at=? WHERE symbol=?",
                (research_priority, beijing_now().isoformat(), symbol),
            )
            if result.rowcount == 0:
                raise KeyError(symbol)
        return self.get(symbol) or {}

    def record_analysis_result(
        self,
        *,
        symbol: str,
        analysis_version: str,
        thesis_hash: str | None,
        summary: str,
        cooldown_until: str | None,
        lifecycle_status: str,
    ) -> dict[str, object]:
        symbol = self._normalize_symbol(symbol)
        now = beijing_now().isoformat()
        run_id = str(uuid4())
        with self.store._connect() as connection:
            if not connection.execute("SELECT 1 FROM candidate_entries WHERE symbol=?", (symbol,)).fetchone():
                raise KeyError(symbol)
            connection.execute(
                """UPDATE candidate_entries SET
                     last_deep_analysis_at=?,analysis_version=?,thesis_hash=?,cooldown_until=?,
                     lifecycle_status=?,updated_at=? WHERE symbol=?""",
                (now, analysis_version, thesis_hash, cooldown_until, lifecycle_status, now, symbol),
            )
            connection.execute(
                """INSERT INTO candidate_analysis_runs(
                     run_id,symbol,status,analysis_version,thesis_hash,summary,started_at,finished_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (run_id, symbol, "completed", analysis_version, thesis_hash, str(summary or ""), now, now),
            )
        self.record_event(
            symbol=symbol,
            event_type="analysis_completed",
            detail={"run_id": run_id, "analysis_version": analysis_version, "thesis_hash": thesis_hash},
        )
        return self.get(symbol) or {}

    def add_activation_rule(
        self,
        *,
        symbol: str,
        rule_type: str,
        metric: str,
        operator: str,
        value: object,
        reason: str,
        source: str,
    ) -> dict[str, object]:
        symbol = self._normalize_symbol(symbol)
        rule_id = str(uuid4())
        now = beijing_now().isoformat()
        with self.store._connect() as connection:
            if not connection.execute("SELECT 1 FROM candidate_entries WHERE symbol=?", (symbol,)).fetchone():
                raise KeyError(symbol)
            connection.execute(
                """INSERT INTO candidate_activation_rules(
                     rule_id,symbol,rule_type,metric,operator,value_json,reason,source,usage_scope,enabled,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rule_id,
                    symbol,
                    rule_type,
                    metric,
                    operator,
                    json.dumps(value, ensure_ascii=False, sort_keys=True),
                    str(reason or ""),
                    str(source or "user"),
                    "RESEARCH_ONLY",
                    1,
                    now,
                    now,
                ),
            )
        return self.activation_rule(rule_id) or {}

    def set_activation_rule_enabled(self, rule_id: str, *, enabled: bool) -> dict[str, object]:
        with self.store._connect() as connection:
            result = connection.execute(
                "UPDATE candidate_activation_rules SET enabled=?,updated_at=? WHERE rule_id=?",
                (1 if enabled else 0, beijing_now().isoformat(), str(rule_id)),
            )
            if result.rowcount == 0:
                raise KeyError(rule_id)
        return self.activation_rule(rule_id) or {}

    def record_event(
        self,
        *,
        symbol: str,
        event_type: str,
        detail: dict[str, object],
        from_status: str | None = None,
        to_status: str | None = None,
    ) -> None:
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO candidate_events(event_id,symbol,event_type,from_status,to_status,detail_json,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    self._normalize_symbol(symbol),
                    str(event_type),
                    from_status,
                    to_status,
                    json.dumps(detail, ensure_ascii=False, sort_keys=True, default=str),
                    beijing_now().isoformat(),
                ),
            )

    def activation_rule(self, rule_id: str) -> dict[str, object] | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM candidate_activation_rules WHERE rule_id=?",
                (str(rule_id),),
            ).fetchone()
        return self._rule_row(row) if row else None

    def activation_rules(self, symbol: str, *, include_disabled: bool = False) -> list[dict[str, object]]:
        symbol = self._normalize_symbol(symbol)
        sql = "SELECT * FROM candidate_activation_rules WHERE symbol=?"
        params: list[object] = [symbol]
        if not include_disabled:
            sql += " AND enabled=1"
        sql += " ORDER BY created_at ASC"
        with self.store._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._rule_row(row) for row in rows]

    def get(self, symbol: str) -> dict[str, object] | None:
        symbol = self._normalize_symbol(symbol)
        with self.store._connect() as connection:
            row = connection.execute("SELECT * FROM candidate_entries WHERE symbol=?", (symbol,)).fetchone()
            if not row:
                return None
            source_rows = connection.execute(
                "SELECT * FROM candidate_sources WHERE symbol=? ORDER BY created_at ASC",
                (symbol,),
            ).fetchall()
            event_rows = connection.execute(
                "SELECT * FROM candidate_events WHERE symbol=? ORDER BY created_at DESC LIMIT 20",
                (symbol,),
            ).fetchall()
        result = dict(row)
        result["sources"] = [dict(item) for item in source_rows]
        result["activation_rules"] = self.activation_rules(symbol, include_disabled=True)
        result["events"] = [
            {
                **dict(item),
                "detail": json.loads(str(item["detail_json"] or "{}")),
            }
            for item in event_rows
        ]
        result["formal_trade_authority"] = False
        return result

    def list(
        self,
        *,
        lifecycle_status: str | None = None,
        research_priority: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
    ) -> list[dict[str, object]]:
        clauses: list[str] = []
        params: list[object] = []
        if lifecycle_status:
            clauses.append("lifecycle_status=?")
            params.append(lifecycle_status)
        elif not include_archived:
            clauses.append("lifecycle_status<>'ARCHIVED'")
        if research_priority:
            clauses.append("research_priority=?")
            params.append(research_priority)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.store._connect() as connection:
            rows = connection.execute(
                f"SELECT symbol FROM candidate_entries{where} ORDER BY research_priority DESC,updated_at DESC LIMIT ?",
                (*params, max(1, min(int(limit), 1000))),
            ).fetchall()
        return [item for row in rows if (item := self.get(str(row["symbol"]))) is not None]

    @staticmethod
    def _rule_row(row) -> dict[str, object]:
        result = dict(row)
        result["value"] = json.loads(str(result.pop("value_json")))
        result["enabled"] = bool(result["enabled"])
        return result
