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


def _create_research_chat_tables(connection: sqlite3.Connection) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS research_chat_sessions (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, primary_symbol TEXT, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS research_chat_turns (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL, client_request_id TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL,
        context_id TEXT, context_hash TEXT, answer_text TEXT NOT NULL DEFAULT '',
        decision_report_id TEXT, error_code TEXT, error_message TEXT,
        prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
        reasoning_tokens INTEGER NOT NULL DEFAULT 0, latency_ms INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_research_chat_turns_session_time ON research_chat_turns(session_id, created_at DESC);
    CREATE TABLE IF NOT EXISTS research_chat_messages (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL, turn_id TEXT NOT NULL, role TEXT NOT NULL,
        content_type TEXT NOT NULL, content TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS research_tool_calls (
        id TEXT PRIMARY KEY, turn_id TEXT NOT NULL, tool_name TEXT NOT NULL, tool_version TEXT NOT NULL,
        arguments_json TEXT NOT NULL, result_summary_json TEXT, status TEXT NOT NULL, duration_ms INTEGER NOT NULL DEFAULT 0,
        error_code TEXT, created_at TEXT NOT NULL, completed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS research_clarifications (
        id TEXT PRIMARY KEY, turn_id TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
        questions_json TEXT NOT NULL, answers_json TEXT, expires_at TEXT NOT NULL, created_at TEXT NOT NULL, answered_at TEXT
    );
    """)

def _create_research_chat_session_sources(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS research_chat_session_sources (session_id TEXT NOT NULL, source_key TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL, PRIMARY KEY(session_id, source_key))")


def _create_research_daily_history_refreshes(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS research_daily_history_refreshes ("
        "session_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, required_days INTEGER NOT NULL, "
        "status TEXT NOT NULL, bar_count INTEGER NOT NULL DEFAULT 0, error_message TEXT, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )


MIGRATIONS = (
    Migration("0001_legacy_schema_baseline", _record_legacy_schema_baseline),
    Migration("0002_decision_contexts", _create_decision_contexts),
    Migration("0003_decision_shadow_reports", _create_decision_shadow_reports),
    Migration("0004_trade_plan_invalidation_price", _add_trade_plan_invalidation_price),
    Migration("0005_decision_ai_runs", _create_decision_ai_runs),
    Migration("0006_decision_reports_and_jobs", _create_decision_reports_and_jobs),
    Migration("0007_research_chat_sessions", _create_research_chat_tables),
    Migration("0008_research_chat_session_sources", _create_research_chat_session_sources),
    Migration("0009_research_daily_history_refreshes", _create_research_daily_history_refreshes),
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
