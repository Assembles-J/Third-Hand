"""Small SQLite persistence layer for the MVP portfolio."""
from __future__ import annotations

import os
import sqlite3
import json
from pathlib import Path
from threading import Lock

from app.time_utils import beijing_now


class PortfolioStore:
    """SQLite-backed portfolio store; it never stores broker credentials or raw CSV files."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or os.getenv("THIRD_HAND_DB_PATH", "data/third_hand.db"))
        self._schema_lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._schema_lock:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS holdings (
                        id TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        name TEXT NOT NULL,
                        quantity REAL NOT NULL CHECK (quantity > 0),
                        average_cost REAL NOT NULL CHECK (average_cost >= 0),
                        created_at TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS holding_drafts (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        quantity REAL NOT NULL CHECK (quantity > 0),
                        average_cost REAL NOT NULL CHECK (average_cost >= 0),
                        created_at TEXT NOT NULL,
                        lookup_status TEXT NOT NULL DEFAULT 'pending',
                        lookup_message TEXT NOT NULL DEFAULT '',
                        lookup_updated_at TEXT
                    )
                """)
                self._ensure_column(connection, "holding_drafts", "lookup_status", "TEXT NOT NULL DEFAULT 'pending'")
                self._ensure_column(connection, "holding_drafts", "lookup_message", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "holding_drafts", "lookup_updated_at", "TEXT")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS symbol_lookup_cache (
                        name TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS market_quote_cache (
                        symbol TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute("CREATE TABLE IF NOT EXISTS ai_analysis_cache (content_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS content_cache (content_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS risk_cache (symbol TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS portfolio_analysis_cache (analysis_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS learning_cases (id TEXT PRIMARY KEY, symbol TEXT, title TEXT NOT NULL, context TEXT NOT NULL, lesson TEXT NOT NULL, outcome TEXT NOT NULL, position_band TEXT NOT NULL DEFAULT '', planned_action TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0.5, evidence_links TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL)")
                self._ensure_column(connection, "learning_cases", "position_band", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "learning_cases", "planned_action", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "learning_cases", "confidence", "REAL NOT NULL DEFAULT 0.5")
                self._ensure_column(connection, "learning_cases", "evidence_links", "TEXT NOT NULL DEFAULT '[]'")

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def list(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM holdings ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def add(self, holding_id: str, symbol: str, name: str, quantity: float, average_cost: float) -> dict[str, object]:
        item = {
            "id": holding_id, "symbol": symbol, "name": name, "quantity": quantity,
            "average_cost": average_cost, "created_at": beijing_now().isoformat(),
        }
        with self._connect() as connection:
            existing = connection.execute("SELECT id FROM holdings WHERE symbol = ? ORDER BY created_at DESC LIMIT 1", (symbol,)).fetchone()
            if existing:
                item["id"] = str(existing["id"])
                connection.execute("UPDATE holdings SET name=:name, quantity=:quantity, average_cost=:average_cost, created_at=:created_at WHERE id=:id", item)
            else:
                connection.execute("INSERT INTO holdings (id, symbol, name, quantity, average_cost, created_at) VALUES (:id, :symbol, :name, :quantity, :average_cost, :created_at)", item)
        return item

    def list_drafts(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM holding_drafts ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def add_draft(self, draft_id: str, name: str, quantity: float, average_cost: float) -> dict[str, object]:
        item = {
            "id": draft_id, "name": name, "quantity": quantity,
            "average_cost": average_cost, "created_at": beijing_now().isoformat(),
            "lookup_status": "pending", "lookup_message": "等待后台查询证券代码", "lookup_updated_at": None,
        }
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO holding_drafts
                (id, name, quantity, average_cost, created_at, lookup_status, lookup_message, lookup_updated_at)
                VALUES (:id, :name, :quantity, :average_cost, :created_at, :lookup_status, :lookup_message, :lookup_updated_at)""",
                item,
            )
        return item

    def add_drafts(self, drafts: list[dict[str, object]]) -> list[dict[str, object]]:
        for draft in drafts:
            draft.setdefault("lookup_status", "pending")
            draft.setdefault("lookup_message", "等待后台查询证券代码")
            draft.setdefault("lookup_updated_at", None)
        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO holding_drafts
                (id, name, quantity, average_cost, created_at, lookup_status, lookup_message, lookup_updated_at)
                VALUES (:id, :name, :quantity, :average_cost, :created_at, :lookup_status, :lookup_message, :lookup_updated_at)""",
                drafts,
            )
        return drafts

    def drafts_by_ids(self, draft_ids: list[str]) -> list[dict[str, object]]:
        if not draft_ids:
            return []
        placeholders = ",".join("?" for _ in draft_ids)
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM holding_drafts WHERE id IN ({placeholders})", draft_ids).fetchall()
        return [dict(row) for row in rows]

    def draft_ids_needing_lookup(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM holding_drafts WHERE lookup_status IN ('pending', 'querying') ORDER BY created_at"
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def mark_drafts_querying(self, draft_ids: list[str]) -> None:
        if not draft_ids:
            return
        timestamp = beijing_now().isoformat()
        placeholders = ",".join("?" for _ in draft_ids)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE holding_drafts SET lookup_status='querying', lookup_message='正在查询证券代码', lookup_updated_at=? WHERE id IN ({placeholders})",
                [timestamp, *draft_ids],
            )

    def set_draft_lookup_status(self, draft_id: str, lookup_status: str, lookup_message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE holding_drafts SET lookup_status=?, lookup_message=?, lookup_updated_at=? WHERE id=?",
                (lookup_status, lookup_message, beijing_now().isoformat(), draft_id),
            )

    def save_symbol_lookups(self, results: list[dict[str, object]]) -> None:
        if not results:
            return
        timestamp = beijing_now().isoformat()
        rows = [
            (str(result["query"]), json.dumps(result.get("matches", []), ensure_ascii=False), timestamp)
            for result in results
        ]
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO symbol_lookup_cache (name, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                rows,
            )

    def confirm_draft(self, draft_id: str, holding_id: str, symbol: str, name: str, quantity: float, average_cost: float) -> dict[str, object] | None:
        item = {
            "id": holding_id, "symbol": symbol, "name": name, "quantity": quantity,
            "average_cost": average_cost, "created_at": beijing_now().isoformat(),
        }
        with self._connect() as connection:
            draft = connection.execute("SELECT id FROM holding_drafts WHERE id = ?", (draft_id,)).fetchone()
            if not draft:
                return None
            existing = connection.execute("SELECT id FROM holdings WHERE symbol = ? ORDER BY created_at DESC LIMIT 1", (symbol,)).fetchone()
            if existing:
                item["id"] = str(existing["id"])
                connection.execute("UPDATE holdings SET name=:name, quantity=:quantity, average_cost=:average_cost, created_at=:created_at WHERE id=:id", item)
            else:
                connection.execute("INSERT INTO holdings (id, symbol, name, quantity, average_cost, created_at) VALUES (:id, :symbol, :name, :quantity, :average_cost, :created_at)", item)
            connection.execute("DELETE FROM holding_drafts WHERE id = ?", (draft_id,))
        return item

    def delete(self, holding_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
        return result.rowcount > 0

    def delete_draft(self, draft_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM holding_drafts WHERE id = ?", (draft_id,))
        return result.rowcount > 0

    def clear_for_test(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM holdings")
            connection.execute("DELETE FROM holding_drafts")
            connection.execute("DELETE FROM market_quote_cache")
            connection.execute("DELETE FROM symbol_lookup_cache")

    def cached_quotes(self, symbols: list[str]) -> list[dict[str, object]]:
        if not symbols:
            return []
        placeholders = ",".join("?" for _ in symbols)
        with self._connect() as connection:
            rows = connection.execute(f"SELECT payload FROM market_quote_cache WHERE symbol IN ({placeholders})", symbols).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def save_quotes(self, quotes: list[dict[str, object]]) -> None:
        if not quotes:
            return
        timestamp = beijing_now().isoformat()
        rows = [(str(quote["symbol"]), json.dumps(quote, ensure_ascii=False, default=str), timestamp) for quote in quotes]
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO market_quote_cache (symbol, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                rows,
            )

    def cached_analysis(self, content_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM ai_analysis_cache WHERE content_id = ?", (content_id,)).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def save_analysis(self, content_id: str, payload: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO ai_analysis_cache (content_id, payload) VALUES (?, ?) ON CONFLICT(content_id) DO UPDATE SET payload=excluded.payload", (content_id, json.dumps(payload, ensure_ascii=False)))

    def save_content(self, items: list[dict[str, object]]) -> None:
        timestamp = beijing_now().isoformat()
        rows = [(str(item["id"]), json.dumps(item, ensure_ascii=False, default=str), timestamp) for item in items]
        with self._connect() as connection:
            connection.executemany("INSERT INTO content_cache (content_id, payload, updated_at) VALUES (?, ?, ?) ON CONFLICT(content_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", rows)

    def save_risk(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO risk_cache (symbol, payload, updated_at) VALUES (?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (str(item["symbol"]), json.dumps(item, ensure_ascii=False, default=str), beijing_now().isoformat()))

    def save_portfolio_analysis(self, payload: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO portfolio_analysis_cache (analysis_key, payload, updated_at) VALUES ('current', ?, ?) ON CONFLICT(analysis_key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (json.dumps(payload, ensure_ascii=False, default=str), beijing_now().isoformat()))

    def cached_risk(self, symbol: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM risk_cache WHERE symbol = ?", (symbol,)).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def add_learning_case(self, item: dict[str, object]) -> dict[str, object]:
        with self._connect() as connection:
            item["evidence_links"] = json.dumps(item.get("evidence_links", []), ensure_ascii=False)
            connection.execute("INSERT INTO learning_cases (id, symbol, title, context, lesson, outcome, position_band, planned_action, confidence, evidence_links, created_at) VALUES (:id,:symbol,:title,:context,:lesson,:outcome,:position_band,:planned_action,:confidence,:evidence_links,:created_at)", item)
        return {**item, "evidence_links": json.loads(str(item["evidence_links"]))}

    def learning_cases(self, symbol: str | None = None) -> list[dict[str, object]]:
        query, params = ("SELECT * FROM learning_cases WHERE symbol=? OR symbol IS NULL ORDER BY created_at DESC", [symbol]) if symbol else ("SELECT * FROM learning_cases ORDER BY created_at DESC", [])
        with self._connect() as connection: rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "evidence_links": json.loads(str(row["evidence_links"]))} for row in rows]
