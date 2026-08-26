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


def _create_p1_data_lineage(connection: sqlite3.Connection) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS data_source_registry (
      source_key TEXT PRIMARY KEY, provider TEXT NOT NULL, data_class TEXT NOT NULL,
      retention_days INTEGER NOT NULL, revision_policy TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS raw_data_snapshots (
      snapshot_id TEXT PRIMARY KEY, source_key TEXT NOT NULL, symbol TEXT, data_class TEXT NOT NULL,
      effective_at TEXT, available_at TEXT NOT NULL, retrieved_at TEXT NOT NULL, payload_hash TEXT NOT NULL,
      payload TEXT NOT NULL, supersedes_snapshot_id TEXT, created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_raw_data_snapshots_lookup ON raw_data_snapshots(symbol, data_class, available_at DESC);
    CREATE TABLE IF NOT EXISTS data_quality_events (
      event_id TEXT PRIMARY KEY, symbol TEXT, source_key TEXT NOT NULL, event_type TEXT NOT NULL,
      severity TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS feature_catalog (
      feature_key TEXT NOT NULL, version TEXT NOT NULL, definition_json TEXT NOT NULL,
      enabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, PRIMARY KEY(feature_key, version)
    );
    CREATE TABLE IF NOT EXISTS feature_values (
      context_id TEXT NOT NULL, feature_key TEXT NOT NULL, feature_version TEXT NOT NULL,
      value_json TEXT NOT NULL, source_snapshot_ids TEXT NOT NULL, effective_at TEXT,
      available_at TEXT NOT NULL, quality_status TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(context_id, feature_key, feature_version)
    );
    """)


def _create_research_reports(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS research_reports (report_id TEXT PRIMARY KEY, context_id TEXT NOT NULL, symbol TEXT NOT NULL, input_hash TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_research_reports_symbol_time ON research_reports(symbol, created_at DESC)")


def _create_research_theses(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS research_thesis_versions (thesis_id TEXT NOT NULL, version INTEGER NOT NULL, symbol TEXT NOT NULL, report_id TEXT NOT NULL, prior_version_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(thesis_id, version))")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_research_theses_symbol_time ON research_thesis_versions(symbol, created_at DESC)")


def _create_simulation_run_audit(connection: sqlite3.Connection) -> None:
    """Persist one run_id per paper-trading pass plus every observable stage.

    A simulation run covers candidate selection, market quotes, daily history,
    risk, news, decision, execution and the final equity snapshot.  Each symbol
    additionally gets a terminal state so a pass that does not trade still has
    an explicit, queryable reason.
    """
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS simulation_runs (
      run_id TEXT PRIMARY KEY,
      trigger TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      symbol_count INTEGER NOT NULL DEFAULT 0,
      generated INTEGER NOT NULL DEFAULT 0,
      executed INTEGER NOT NULL DEFAULT 0,
      skipped INTEGER NOT NULL DEFAULT 0,
      message TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_simulation_runs_started ON simulation_runs(started_at DESC);
    CREATE TABLE IF NOT EXISTS simulation_run_stages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      stage TEXT NOT NULL,
      symbol TEXT,
      status TEXT NOT NULL,
      detail TEXT NOT NULL DEFAULT '{}',
      started_at TEXT NOT NULL,
      finished_at TEXT,
      elapsed_ms INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_simulation_run_stages_run ON simulation_run_stages(run_id, stage, symbol);
    CREATE TABLE IF NOT EXISTS simulation_run_symbols (
      run_id TEXT NOT NULL,
      symbol TEXT NOT NULL,
      terminal_state TEXT NOT NULL,
      detail TEXT NOT NULL DEFAULT '{}',
      updated_at TEXT NOT NULL,
      PRIMARY KEY (run_id, symbol)
    );
    CREATE INDEX IF NOT EXISTS idx_simulation_run_symbols_symbol ON simulation_run_symbols(symbol, updated_at DESC);
    CREATE TABLE IF NOT EXISTS daily_history_provider_attempts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT,
      trigger TEXT,
      symbol TEXT NOT NULL,
      provider TEXT NOT NULL,
      status TEXT NOT NULL,
      started_at TEXT NOT NULL,
      elapsed_ms INTEGER NOT NULL DEFAULT 0,
      bar_count INTEGER NOT NULL DEFAULT 0,
      error_type TEXT,
      error_message TEXT,
      detail TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_daily_history_attempts_symbol_time ON daily_history_provider_attempts(symbol, started_at DESC);
    CREATE INDEX IF NOT EXISTS idx_daily_history_attempts_run ON daily_history_provider_attempts(run_id);
    """)


def _create_data_provider_health(connection: sqlite3.Connection) -> None:
    """Track per-provider health and circuit state for daily-history sources.

    A provider opens its circuit after repeated failures and stays closed for a
    cooldown; a successful attempt closes it again.  The table also powers the
    auto-backfill queue so stocks that failed data preparation are retried
    after the provider recovers.
    """
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS data_provider_health (
      provider TEXT PRIMARY KEY,
      circuit_state TEXT NOT NULL DEFAULT 'closed',
      consecutive_failures INTEGER NOT NULL DEFAULT 0,
      total_attempts INTEGER NOT NULL DEFAULT 0,
      total_success INTEGER NOT NULL DEFAULT 0,
      total_failures INTEGER NOT NULL DEFAULT 0,
      last_attempt_at TEXT,
      last_success_at TEXT,
      last_failure_at TEXT,
      circuit_opened_at TEXT,
      cooldown_until TEXT,
      error_type TEXT,
      error_message TEXT,
      updated_at TEXT NOT NULL
    );
    """)


def _retire_fx_rate_cache(_: sqlite3.Connection) -> None:
    """Keep migration ordering stable after retiring the unused FX cache.

    Older local databases may retain the table created by the original 0015
    migration. It is deliberately ignored rather than dropped, so upgrading is
    non-destructive and no historical decision data is altered.
    """


def _create_broker_settlement_receipts(connection: sqlite3.Connection) -> None:
    """Keep broker-reported Stock Connect settlement facts separate from rules."""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS broker_settlement_receipts ("
        "receipt_id TEXT PRIMARY KEY, decision_id TEXT, symbol TEXT NOT NULL, market TEXT NOT NULL, "
        "side TEXT NOT NULL, quantity REAL NOT NULL, trade_price REAL NOT NULL, trade_currency TEXT NOT NULL, "
        "settlement_currency TEXT NOT NULL, gross_settlement_amount REAL NOT NULL, commission REAL, "
        "stamp_duty REAL, other_fee REAL, total_fee REAL NOT NULL, net_settlement_amount REAL NOT NULL, "
        "implied_fx_rate REAL NOT NULL, broker TEXT NOT NULL, occurred_at TEXT NOT NULL, "
        "source_reference TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_broker_settlement_receipts_symbol_time "
        "ON broker_settlement_receipts(symbol, occurred_at DESC)"
    )


def _create_paper_execution_safety_contract(connection: sqlite3.Connection) -> None:
    """Additive persistence for T+1 display and idempotent deferrals."""
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(paper_position_lots)")}
    if "sellable_at" not in columns:
        connection.execute("ALTER TABLE paper_position_lots ADD COLUMN sellable_at TEXT")
    # Materialize a deterministic timestamp for legacy lots. A malformed legacy
    # timestamp deliberately remains NULL and therefore non-sellable until the
    # existing reconciliation path can establish its provenance.
    from app.trading_calendar import TradingCalendarService
    calendar = TradingCalendarService()
    pending_rows = connection.execute(
        "SELECT lot_id,market,acquired_at FROM paper_position_lots "
        "WHERE sellable_at IS NULL AND settlement_state='PENDING_T1'"
    ).fetchall()
    for lot_id, market, acquired_at in pending_rows:
        try:
            acquired = datetime.fromisoformat(str(acquired_at).replace("Z", "+00:00"))
            if acquired.tzinfo is None:
                acquired = acquired.replace(tzinfo=timezone.utc)
            next_open = calendar.next_session_open(str(market).upper(), acquired)
        except (TypeError, ValueError):
            next_open = None
        if next_open is not None:
            connection.execute(
                "UPDATE paper_position_lots SET sellable_at=? WHERE lot_id=?",
                (next_open.isoformat(), str(lot_id)),
            )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_paper_position_lots_sellable_at "
        "ON paper_position_lots(symbol, sellable_at)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS paper_execution_deferrals ("
        "decision_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, action TEXT NOT NULL, "
        "requested_quantity REAL NOT NULL, max_executable_quantity REAL NOT NULL, "
        "reason_code TEXT NOT NULL, next_eligible_at TEXT NOT NULL, state TEXT NOT NULL, "
        "created_at TEXT NOT NULL, resolved_at TEXT, detail TEXT NOT NULL DEFAULT '{}'"
        ")"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_paper_execution_deferrals_symbol_state_time "
        "ON paper_execution_deferrals(symbol, state, next_eligible_at)"
    )


def _create_paper_position_episodes(connection: sqlite3.Connection) -> None:
    """Persist the frozen entry contract for every paper-position episode."""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS paper_position_episodes ("
        "episode_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, entry_decision_id TEXT, "
        "entry_evidence_snapshot_hash TEXT, entry_research_assessment_hash TEXT, "
        "entry_risk_state TEXT NOT NULL DEFAULT '{}', entry_technical_state TEXT NOT NULL DEFAULT '{}', "
        "entry_market_regime TEXT NOT NULL DEFAULT '{}', entry_event_state TEXT NOT NULL DEFAULT '{}', "
        "entry_price REAL NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT, detail TEXT NOT NULL DEFAULT '{}'"
        ")"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_paper_position_episodes_active "
        "ON paper_position_episodes(symbol, closed_at, opened_at DESC)"
    )


def _add_pux1_watchlist_metadata(connection: sqlite3.Connection) -> None:
    """Add durable user-attention metadata to the existing Watchlist table."""
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(watchlist)")}
    if "enabled" not in columns:
        connection.execute("ALTER TABLE watchlist ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
    if "priority" not in columns:
        connection.execute("ALTER TABLE watchlist ADD COLUMN priority TEXT NOT NULL DEFAULT 'NORMAL'")
    if "note" not in columns:
        connection.execute("ALTER TABLE watchlist ADD COLUMN note TEXT NOT NULL DEFAULT ''")


def _create_pux2_review_plans(connection: sqlite3.Connection) -> None:
    """Persist append-only, versioned review permission decisions."""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS review_plans ("
        "plan_id TEXT PRIMARY KEY, policy_version TEXT NOT NULL, symbol TEXT NOT NULL, "
        "evaluated_at TEXT NOT NULL, review_mode TEXT NOT NULL, analysis_depth TEXT NOT NULL, "
        "reason_codes TEXT NOT NULL, last_review_at TEXT, next_review_at TEXT, "
        "routine_full_research_available INTEGER NOT NULL, budget_override INTEGER NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_review_plans_symbol_time "
        "ON review_plans(symbol, evaluated_at DESC)"
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
    Migration("0010_p1_data_lineage", _create_p1_data_lineage),
    Migration("0011_research_reports", _create_research_reports),
    Migration("0012_research_theses", _create_research_theses),
    Migration("0013_simulation_run_audit", _create_simulation_run_audit),
    Migration("0014_data_provider_health", _create_data_provider_health),
    Migration("0015_fx_rate_cache", _retire_fx_rate_cache),
    Migration("0016_broker_settlement_receipts", _create_broker_settlement_receipts),
    Migration("0017_paper_execution_safety_contract", _create_paper_execution_safety_contract),
    Migration("0018_paper_position_episodes", _create_paper_position_episodes),
    Migration("0019_pux1_watchlist_metadata", _add_pux1_watchlist_metadata),
    Migration("0020_pux2_review_plans", _create_pux2_review_plans),
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
