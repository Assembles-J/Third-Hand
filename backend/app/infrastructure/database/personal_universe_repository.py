"""SQLite-backed persistence for Personal Universe watchlist metadata.

The existing ``PortfolioStore`` remains the database owner. This repository is a
feature adapter around that same database; it does not introduce a second store.
"""
from __future__ import annotations

import json

from app.domain.personal_universe import WatchlistEntry, WatchlistPriority
from app.time_utils import beijing_now


class PersonalUniverseRepository:
    def __init__(self, store) -> None:
        self.store = store

    def list_watchlist(self, *, include_disabled: bool = False) -> list[WatchlistEntry]:
        query = "SELECT * FROM watchlist"
        params: tuple[object, ...] = ()
        if not include_disabled:
            query += " WHERE enabled = 1"
        query += " ORDER BY CASE priority WHEN 'CORE' THEN 0 WHEN 'FOCUS' THEN 1 ELSE 2 END, updated_at DESC, symbol ASC"
        with self.store._connect() as connection:  # feature adapter over existing store ownership
            rows = connection.execute(query, params).fetchall()
        return [WatchlistEntry.from_record(dict(row)) for row in rows]

    def watchlist_item(self, symbol: str) -> WatchlistEntry | None:
        canonical = symbol.strip().upper()
        with self.store._connect() as connection:
            row = connection.execute("SELECT * FROM watchlist WHERE symbol = ?", (canonical,)).fetchone()
        return WatchlistEntry.from_record(dict(row)) if row is not None else None

    def upsert_watchlist_item(
        self,
        symbol: str,
        name: str,
        *,
        enabled: bool = True,
        priority: WatchlistPriority = WatchlistPriority.NORMAL,
        note: str = "",
    ) -> WatchlistEntry:
        canonical = symbol.strip().upper()
        display_name = name.strip()
        if not canonical:
            raise ValueError("symbol is required")
        if not display_name:
            raise ValueError("name is required")
        clean_note = note.strip()
        if len(clean_note) > 500:
            raise ValueError("watchlist note must not exceed 500 characters")
        now = beijing_now().isoformat()
        with self.store._connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM watchlist WHERE symbol = ?",
                (canonical,),
            ).fetchone()
            created_at = str(existing["created_at"]) if existing else now
            connection.execute(
                "INSERT INTO watchlist (symbol,name,enabled,priority,note,created_at,updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET "
                "name=excluded.name, enabled=excluded.enabled, priority=excluded.priority, "
                "note=excluded.note, updated_at=excluded.updated_at",
                (
                    canonical,
                    display_name,
                    1 if enabled else 0,
                    priority.value,
                    clean_note,
                    created_at,
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM watchlist WHERE symbol = ?", (canonical,)).fetchone()
        return WatchlistEntry.from_record(dict(row))

    def update_watchlist_item(
        self,
        symbol: str,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        priority: WatchlistPriority | None = None,
        note: str | None = None,
    ) -> WatchlistEntry | None:
        current = self.watchlist_item(symbol)
        if current is None:
            return None
        next_name = current.name if name is None else name.strip()
        next_enabled = current.enabled if enabled is None else enabled
        next_priority = current.priority if priority is None else priority
        next_note = current.note if note is None else note.strip()
        return self.upsert_watchlist_item(
            current.symbol,
            next_name,
            enabled=next_enabled,
            priority=next_priority,
            note=next_note,
        )

    def delete_watchlist_item(self, symbol: str) -> bool:
        canonical = symbol.strip().upper()
        with self.store._connect() as connection:
            result = connection.execute("DELETE FROM watchlist WHERE symbol = ?", (canonical,))
        return result.rowcount > 0

    def instrument_markets(self, symbols: list[str]) -> dict[str, str]:
        canonical = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        if not canonical:
            return {}
        placeholders = ",".join("?" for _ in canonical)
        with self.store._connect() as connection:
            rows = connection.execute(
                f"SELECT symbol, market FROM instrument_metadata WHERE symbol IN ({placeholders})",
                canonical,
            ).fetchall()
        return {str(row["symbol"]).upper(): str(row["market"]).upper() for row in rows}

    def latest_decisions(self, symbols: list[str]) -> dict[str, dict[str, object]]:
        """Read the newest persisted Formal Decision per symbol without re-running it."""
        canonical = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        if not canonical:
            return {}
        placeholders = ",".join("?" for _ in canonical)
        with self.store._connect() as connection:
            rows = connection.execute(
                f"SELECT symbol,payload,created_at FROM decision_reports "
                f"WHERE symbol IN ({placeholders}) ORDER BY symbol ASC, created_at DESC",
                canonical,
            ).fetchall()
        latest: dict[str, dict[str, object]] = {}
        for row in rows:
            symbol = str(row["symbol"]).strip().upper()
            if symbol in latest:
                continue
            try:
                payload = json.loads(str(row["payload"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            latest[symbol] = {**payload, "_persisted_created_at": str(row["created_at"])}
        return latest
