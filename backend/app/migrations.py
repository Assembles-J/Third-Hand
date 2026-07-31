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


def _create_decision_contexts(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS decision_contexts ("
        "context_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, input_hash TEXT NOT NULL, "
        "payload TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_decision_contexts_symbol_created "
        "ON decision_contexts(symbol, created_at DESC)"
    )


def _create_decision_shadow_reports(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS decision_shadow_reports ("
        "shadow_id TEXT PRIMARY KEY, context_id TEXT NOT NULL, symbol TEXT NOT NULL, "
        "input_hash TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_decision_shadow_reports_symbol_created "
        "ON decision_shadow_reports(symbol, created_at DESC)"
    )


def _add_trade_plan_invalidation_price(connection: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(trade_plans)")}
    if "invalidation_price" not in columns:
        connection.execute("ALTER TABLE trade_plans ADD COLUMN invalidation_price REAL")


def _create_decision_ai_runs(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS decision_ai_runs (run_id TEXT PRIMARY KEY, context_id TEXT NOT NULL, input_hash TEXT NOT NULL, status TEXT NOT NULL, error_code TEXT, payload TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL)")


def _create_decision_reports_and_jobs(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS decision_reports (decision_id TEXT PRIMARY KEY, context_id TEXT NOT NULL, symbol TEXT NOT NULL, input_hash TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS decision_jobs (job_id TEXT PRIMARY KEY, context_id TEXT NOT NULL, symbol TEXT NOT NULL, input_hash TEXT NOT NULL UNIQUE, status TEXT NOT NULL, attempts INTEGER NOT NULL, payload TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")


MIGRATIONS = (
    Migration("0001_legacy_schema_baseline", _record_legacy_schema_baseline),
    Migration("0002_decision_contexts", _create_decision_contexts),
    Migration("0003_decision_shadow_reports", _create_decision_shadow_reports),
    Migration("0004_trade_plan_invalidation_price", _add_trade_plan_invalidation_price),
    Migration("0005_decision_ai_runs", _create_decision_ai_runs),
    Migration("0006_decision_reports_and_jobs", _create_decision_reports_and_jobs),
)


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
