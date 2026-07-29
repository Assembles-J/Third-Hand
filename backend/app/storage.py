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
                        created_at TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS market_quote_cache (
                        symbol TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

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
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO holding_drafts (id, name, quantity, average_cost, created_at) VALUES (:id, :name, :quantity, :average_cost, :created_at)",
                item,
            )
        return item

    def add_drafts(self, drafts: list[dict[str, object]]) -> list[dict[str, object]]:
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO holding_drafts (id, name, quantity, average_cost, created_at) VALUES (:id, :name, :quantity, :average_cost, :created_at)",
                drafts,
            )
        return drafts

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
