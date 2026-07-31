"""Small, idempotent SQLite migration runner.

The existing ``PortfolioStore`` owns the legacy schema bootstrap. This runner
starts a durable migration ledger without changing that bootstrap or any
application behaviour.
"""
from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Migration:
    migration_id: str
    apply: Callable[[sqlite3.Connection], None]


def _record_legacy_schema_baseline(_connection: sqlite3.Connection) -> None:
    """Mark the pre-runner schema as the migration baseline."""


MIGRATIONS = (Migration("0001_legacy_schema_baseline", _record_legacy_schema_baseline),)


def run_migrations(database_path: str | Path) -> list[str]:
    """Apply outstanding migrations once and return their identifiers."""
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"database does not exist: {path}")

    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            str(row[0])
            for row in connection.execute("SELECT migration_id FROM schema_migrations")
        }
        completed: list[str] = []
        for migration in MIGRATIONS:
            if migration.migration_id in applied:
                continue
            migration.apply(connection)
            connection.execute(
                "INSERT INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)",
                (migration.migration_id, datetime.now(timezone.utc).isoformat()),
            )
            completed.append(migration.migration_id)
    return completed


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Third-Hand SQLite migrations")
    parser.add_argument("--database", required=True, help="existing SQLite database path")
    args = parser.parse_args()
    for migration_id in run_migrations(args.database):
        print(f"applied {migration_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
