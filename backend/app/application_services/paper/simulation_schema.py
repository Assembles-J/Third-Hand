"""Compatibility bootstrap for paper-simulation epochs.

The project is still extracting v2 persistence from the legacy PortfolioStore.
Until that repository owns its own migration runner, this small idempotent schema
bootstrap keeps the new paper-session table local to the v2 feature and seeds one
legacy epoch without rewriting any historical trading evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone


def ensure_paper_simulation_epoch_schema(store) -> None:
    with store._connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS paper_simulation_epochs ("
            "epoch_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE, status TEXT NOT NULL, "
            "started_at TEXT NOT NULL, ended_at TEXT, initial_cash REAL NOT NULL, "
            "end_total_equity REAL, end_cash REAL, end_market_value REAL, "
            "restart_request_id TEXT UNIQUE, archive_payload TEXT NOT NULL DEFAULT '{}', "
            "created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_simulation_epochs_status_sequence "
            "ON paper_simulation_epochs(status, sequence DESC)"
        )
        active = connection.execute(
            "SELECT epoch_id FROM paper_simulation_epochs WHERE status='active' LIMIT 1"
        ).fetchone()
        if active is not None:
            return

        timestamps: list[str] = []
        for table, column in (
            ("paper_trading_logs", "executed_at"),
            ("paper_trading_equity_snapshots", "recorded_at"),
            ("simulation_runs", "started_at"),
            ("paper_trading_cash_flows", "occurred_at"),
        ):
            row = connection.execute(f"SELECT MIN({column}) AS value FROM {table}").fetchone()
            if row and row["value"]:
                timestamps.append(str(row["value"]))
        now = datetime.now(timezone.utc).isoformat()
        started_at = min(timestamps) if timestamps else now

        account = connection.execute(
            "SELECT initial_cash FROM paper_trading_accounts WHERE account_id='default'"
        ).fetchone()
        cash = connection.execute(
            "SELECT available_cash FROM account_cash WHERE account_id='default'"
        ).fetchone()
        stored_initial = float(account["initial_cash"]) if account else 0.0
        available_cash = float(cash["available_cash"]) if cash else 0.0
        initial_cash = stored_initial if stored_initial > 0 else max(0.0, available_cash)
        connection.execute(
            "INSERT INTO paper_simulation_epochs "
            "(epoch_id,sequence,status,started_at,ended_at,initial_cash,end_total_equity,end_cash,end_market_value,restart_request_id,archive_payload,created_at) "
            "VALUES ('legacy-epoch-1',1,'active',?,NULL,?,NULL,NULL,NULL,NULL,'{}',?)",
            (started_at, initial_cash, now),
        )
