from __future__ import annotations

import sqlite3

from app.migrations import MIGRATIONS, run_migrations


def test_pux1_watchlist_metadata_migrates_legacy_rows_once(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE watchlist ("
            "symbol TEXT PRIMARY KEY, name TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO watchlist(symbol,name,created_at,updated_at) VALUES (?,?,?,?)",
            (
                "01810",
                "小米集团-W",
                "2026-08-20T09:00:00+08:00",
                "2026-08-20T09:00:00+08:00",
            ),
        )
        connection.execute(
            "CREATE TABLE schema_migrations ("
            "migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        prior_ids = [
            migration.migration_id
            for migration in MIGRATIONS
            if migration.migration_id != "0019_pux1_watchlist_metadata"
        ]
        connection.executemany(
            "INSERT INTO schema_migrations(migration_id, applied_at) VALUES (?,?)",
            [(migration_id, "2026-08-20T00:00:00+00:00") for migration_id in prior_ids],
        )

    assert run_migrations(database) == ["0019_pux1_watchlist_metadata"]

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        columns = {
            str(row["name"]): row
            for row in connection.execute("PRAGMA table_info(watchlist)")
        }
        row = connection.execute(
            "SELECT symbol,name,enabled,priority,note,created_at,updated_at "
            "FROM watchlist WHERE symbol='01810'"
        ).fetchone()

    assert {"enabled", "priority", "note"}.issubset(columns)
    assert dict(row) == {
        "symbol": "01810",
        "name": "小米集团-W",
        "enabled": 1,
        "priority": "NORMAL",
        "note": "",
        "created_at": "2026-08-20T09:00:00+08:00",
        "updated_at": "2026-08-20T09:00:00+08:00",
    }
    assert run_migrations(database) == []
