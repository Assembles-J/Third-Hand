"""Small SQLite persistence layer for the MVP portfolio."""
from __future__ import annotations

import os
import sqlite3
import json
import math
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.time_utils import beijing_now
from app.decimal_utils import decimal_text


class PortfolioStore:
    """SQLite-backed portfolio store; it never stores broker credentials or raw CSV files."""

    SQLITE_BUSY_TIMEOUT_SECONDS = 15

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or os.getenv("THIRD_HAND_DB_PATH", "data/third_hand.db"))
        self._schema_lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        # Background refreshes and foreground changes use separate connections.
        # Wait for an active writer instead of surfacing ordinary contention as
        # a 500 response.
        connection = sqlite3.connect(self.database_path, timeout=self.SQLITE_BUSY_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self.SQLITE_BUSY_TIMEOUT_SECONDS * 1000}")
        return connection

    def _initialize(self) -> None:
        with self._schema_lock:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                # WAL lets readers continue while a writer commits. SQLite
                # still has one writer, so retain the busy timeout above.
                connection.execute("PRAGMA journal_mode = WAL")
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
                        client_row_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        quantity REAL NOT NULL CHECK (quantity > 0),
                        average_cost REAL NOT NULL CHECK (average_cost >= 0),
                        ocr_confidence REAL,
                        created_at TEXT NOT NULL,
                        lookup_status TEXT NOT NULL DEFAULT 'pending',
                        lookup_message TEXT NOT NULL DEFAULT '',
                        lookup_updated_at TEXT,
                        candidates_json TEXT NOT NULL DEFAULT '[]'
                    )
                """)
                self._ensure_column(connection, "holding_drafts", "client_row_id", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "holding_drafts", "ocr_confidence", "REAL")
                self._ensure_column(connection, "holding_drafts", "lookup_status", "TEXT NOT NULL DEFAULT 'pending'")
                self._ensure_column(connection, "holding_drafts", "lookup_message", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "holding_drafts", "lookup_updated_at", "TEXT")
                self._ensure_column(connection, "holding_drafts", "candidates_json", "TEXT NOT NULL DEFAULT '[]'")
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
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS watchlist (
                        symbol TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS market_quote_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        recorded_at TEXT NOT NULL
                    )
                """)
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_market_quote_history_symbol_time "
                    "ON market_quote_history(symbol, recorded_at DESC)"
                )
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS system_settings (
                        setting_key TEXT PRIMARY KEY,
                        setting_value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute("CREATE TABLE IF NOT EXISTS ai_analysis_cache (content_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS ai_analysis_cache_v2 (
                        cache_key TEXT PRIMARY KEY,
                        content_id TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        input_hash TEXT NOT NULL,
                        rules_hash TEXT NOT NULL,
                        user_context_hash TEXT NOT NULL,
                        model TEXT NOT NULL,
                        prompt_version TEXT NOT NULL,
                        schema_version TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ai_analysis_cache_v2_content_id "
                    "ON ai_analysis_cache_v2(content_id)"
                )
                self._ensure_column(connection, "ai_analysis_cache_v2", "rules_hash", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(
                    connection,
                    "ai_analysis_cache_v2",
                    "user_context_hash",
                    "TEXT NOT NULL DEFAULT ''",
                )
                connection.execute("CREATE TABLE IF NOT EXISTS content_cache (content_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS market_intelligence_cache (
                        cache_key TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS glossary_entries (
                        term_key TEXT PRIMARY KEY,
                        term TEXT NOT NULL,
                        plain_explanation TEXT NOT NULL,
                        watch_for TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT 'user',
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS glossary_lookup_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        term_key TEXT NOT NULL,
                        term TEXT NOT NULL,
                        context TEXT NOT NULL DEFAULT '',
                        found INTEGER NOT NULL,
                        looked_up_at TEXT NOT NULL
                    )
                """)
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_glossary_lookup_history_term_time "
                    "ON glossary_lookup_history(term_key, looked_up_at DESC)"
                )
                connection.execute("CREATE TABLE IF NOT EXISTS risk_cache (symbol TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS daily_price_cache (
                        symbol TEXT NOT NULL,
                        trading_date TEXT NOT NULL,
                        open TEXT,
                        close REAL NOT NULL,
                        high REAL,
                        low REAL,
                        volume TEXT,
                        amount TEXT,
                        amplitude_percent TEXT,
                        change_percent TEXT,
                        change_amount TEXT,
                        turnover_rate TEXT,
                        adjustment TEXT NOT NULL DEFAULT 'qfq',
                        source TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (symbol, trading_date)
                    )
                """)
                # SQLite ALTER TABLE keeps existing installations in place.
                self._ensure_column(connection, "daily_price_cache", "open", "TEXT")
                self._ensure_column(connection, "daily_price_cache", "volume", "TEXT")
                self._ensure_column(connection, "daily_price_cache", "amount", "TEXT")
                self._ensure_column(connection, "daily_price_cache", "amplitude_percent", "TEXT")
                self._ensure_column(connection, "daily_price_cache", "change_percent", "TEXT")
                self._ensure_column(connection, "daily_price_cache", "change_amount", "TEXT")
                self._ensure_column(connection, "daily_price_cache", "turnover_rate", "TEXT")
                self._ensure_column(connection, "daily_price_cache", "adjustment", "TEXT NOT NULL DEFAULT 'qfq'")
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_daily_price_cache_symbol_date "
                    "ON daily_price_cache(symbol, trading_date DESC)"
                )
                connection.execute("CREATE TABLE IF NOT EXISTS intraday_price_cache (symbol TEXT NOT NULL, bar_time TEXT NOT NULL, open REAL NOT NULL, close REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, volume REAL, amount REAL, average_price REAL, source TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(symbol, bar_time))")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_intraday_price_cache_symbol_time ON intraday_price_cache(symbol, bar_time DESC)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS instrument_metadata (
                        symbol TEXT PRIMARY KEY,
                        market TEXT NOT NULL,
                        currency TEXT NOT NULL,
                        lot_size INTEGER,
                        price_tick TEXT,
                        source TEXT NOT NULL,
                        as_of TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute("CREATE TABLE IF NOT EXISTS portfolio_analysis_cache (analysis_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS learning_cases (id TEXT PRIMARY KEY, symbol TEXT, title TEXT NOT NULL, context TEXT NOT NULL, lesson TEXT NOT NULL, outcome TEXT NOT NULL, position_band TEXT NOT NULL DEFAULT '', planned_action TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0.5, evidence_links TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS research_rules (id TEXT PRIMARY KEY, category TEXT NOT NULL, title TEXT NOT NULL, trigger_text TEXT NOT NULL, guidance TEXT NOT NULL, confidence_ceiling REAL NOT NULL, source_url TEXT NOT NULL, version TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS personal_rules (id TEXT PRIMARY KEY, scope TEXT NOT NULL, symbol TEXT, max_position_percent REAL NOT NULL, loss_review_percent REAL NOT NULL, volatility_review_percent REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS trade_plans (
                        id TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL UNIQUE,
                        horizon TEXT NOT NULL,
                        thesis TEXT NOT NULL,
                        market_expectation TEXT NOT NULL,
                        benchmark_symbol TEXT,
                        benchmark_name TEXT,
                        catalysts_json TEXT NOT NULL,
                        entry_condition TEXT NOT NULL,
                        add_condition TEXT NOT NULL,
                        reduce_condition TEXT NOT NULL,
                        exit_condition TEXT NOT NULL,
                        max_position_percent REAL NOT NULL,
                        risk_budget_percent REAL NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        version INTEGER NOT NULL DEFAULT 1,
                        updated_at TEXT NOT NULL
                    )
                """)
                self._ensure_column(connection, "trade_plans", "benchmark_symbol", "TEXT")
                self._ensure_column(connection, "trade_plans", "benchmark_name", "TEXT")
                self._ensure_column(connection, "trade_plans", "structured_conditions_json", "TEXT NOT NULL DEFAULT '[]'")
                connection.execute("CREATE TABLE IF NOT EXISTS analysis_runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS sale_records (
                        id TEXT PRIMARY KEY, holding_id TEXT NOT NULL, symbol TEXT NOT NULL, name TEXT NOT NULL,
                        quantity REAL NOT NULL, sale_price REAL NOT NULL, average_cost REAL NOT NULL,
                        proceeds REAL NOT NULL, cost_basis REAL NOT NULL, realized_pnl REAL NOT NULL,
                        realized_pnl_percent REAL NOT NULL, remaining_quantity REAL NOT NULL,
                        reason TEXT NOT NULL DEFAULT '', analysis_snapshot TEXT NOT NULL DEFAULT '{}', sold_at TEXT NOT NULL
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_sale_records_symbol_time ON sale_records(symbol, sold_at DESC)")
                connection.execute("CREATE TABLE IF NOT EXISTS daily_reviews (id TEXT PRIMARY KEY, review_date TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS ai_jobs (id TEXT PRIMARY KEY, target_id TEXT NOT NULL, input_hash TEXT NOT NULL UNIQUE, status TEXT NOT NULL, attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL, payload TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS account_cash (account_id TEXT PRIMARY KEY, available_cash REAL NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_accounts (account_id TEXT PRIMARY KEY, available_cash REAL NOT NULL, initial_cash REAL NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_cash_flows (id TEXT PRIMARY KEY, amount REAL NOT NULL, flow_type TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', occurred_at TEXT NOT NULL)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_paper_cash_flows_time ON paper_trading_cash_flows(occurred_at DESC)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_positions (symbol TEXT PRIMARY KEY, name TEXT NOT NULL, quantity REAL NOT NULL, average_cost REAL NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS paper_position_lots (
                        lot_id TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        market TEXT NOT NULL,
                        currency TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        acquired_at TEXT NOT NULL,
                        cost_basis REAL NOT NULL,
                        sellable_quantity REAL NOT NULL,
                        settlement_state TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_paper_position_lots_symbol_acquired "
                    "ON paper_position_lots(symbol, acquired_at, lot_id)"
                )
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_logs (id TEXT PRIMARY KEY, symbol TEXT NOT NULL, name TEXT NOT NULL, side TEXT NOT NULL, quantity REAL NOT NULL, price REAL NOT NULL, fee REAL NOT NULL DEFAULT 0, cash_before REAL NOT NULL, cash_after REAL NOT NULL, decision_id TEXT, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'executed', executed_at TEXT NOT NULL)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_paper_trading_logs_symbol_time ON paper_trading_logs(symbol, executed_at DESC)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_equity_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, total_equity REAL NOT NULL, available_cash REAL NOT NULL, market_value REAL NOT NULL, total_pnl REAL NOT NULL, recorded_at TEXT NOT NULL)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_paper_equity_snapshots_time ON paper_trading_equity_snapshots(recorded_at DESC)")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS feedback_events (
                        feedback_id TEXT PRIMARY KEY,
                        decision_id TEXT NOT NULL,
                        decision_input_hash TEXT NOT NULL,
                        execution_log_id TEXT,
                        user_action TEXT NOT NULL,
                        execution_time TEXT,
                        quantity REAL,
                        price REAL,
                        actual_outcome_json TEXT NOT NULL,
                        hypothetical_outcome_json TEXT NOT NULL,
                        explicit_feedback TEXT,
                        review_label TEXT,
                        policy_version TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_feedback_events_decision_time ON feedback_events(decision_id, created_at DESC)")
                self._ensure_column(connection, "paper_trading_logs", "status", "TEXT NOT NULL DEFAULT 'executed'")
                self._ensure_column(connection, "paper_trading_logs", "fee", "REAL NOT NULL DEFAULT 0")
                self._ensure_column(connection, "paper_trading_logs", "execution_quote_at", "TEXT")
                self._ensure_column(connection, "paper_trading_logs", "execution_quote_source", "TEXT")
                self._ensure_column(connection, "paper_trading_logs", "fill_price_mode", "TEXT")
                self._ensure_column(connection, "paper_trading_accounts", "initial_cash", "REAL NOT NULL DEFAULT 0")
                self._ensure_column(connection, "learning_cases", "position_band", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "learning_cases", "planned_action", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "learning_cases", "confidence", "REAL NOT NULL DEFAULT 0.5")
                self._ensure_column(connection, "learning_cases", "evidence_links", "TEXT NOT NULL DEFAULT '[]'")
                self._seed_research_rules(connection)
            # New schema changes are registered independently from this legacy
            # bootstrap so migrations remain auditable and repeatable.
            from app.migrations import run_migrations
            run_migrations(self.database_path)

    @staticmethod
    def _seed_research_rules(connection: sqlite3.Connection) -> None:
        rules = [
            ("position-cap","仓位","单一标的集中度","单一标的占比超过个人预设上限","先复核集中度与相关性；不以单日涨跌作为增加暴露理由。",0.8,"https://investor.sse.com.cn/","v1"),
            ("event-verify","公告","重大公告核验","出现业绩预告、回购、减持、诉讼或监管事件","优先打开正式公告，核验主体、金额、期限和适用范围。",0.9,"https://www.cninfo.com.cn/","v1"),
            ("loss-review","风险","成本大幅偏离","现价较成本显著下跌","先区分市场波动、基本面变化和流动性风险；复核仓位上限，不追补。",0.75,"https://investor.sse.com.cn/","v1"),
            ("valuation-context","估值","估值口径","使用PE/PB等估值指标","核验盈利质量、一次性损益与行业可比性；亏损企业不以PE单独判断。",0.75,"https://www.sse.com.cn/","v1"),
            ("etf-risk","ETF","ETF跟踪风险","持有行业或主题ETF","核验跟踪指数、成分集中度、规模、流动性及折溢价，避免把ETF视作天然分散。",0.85,"https://www.csindex.com.cn/","v1"),
            ("news-not-fact","信息","新闻与事实边界","新闻来源非正式披露","新闻仅作线索；关键事实以交易所、巨潮或公司公告原文为准。",0.95,"https://www.cninfo.com.cn/","v1"),
        ]
        connection.executemany("INSERT OR IGNORE INTO research_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rules)

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
            existing = connection.execute("SELECT id, created_at FROM holdings WHERE symbol = ? ORDER BY created_at DESC LIMIT 1", (symbol,)).fetchone()
            if existing:
                item["id"] = str(existing["id"])
                item["created_at"] = str(existing["created_at"])
                connection.execute("UPDATE holdings SET name=:name, quantity=:quantity, average_cost=:average_cost WHERE id=:id", item)
            else:
                connection.execute("INSERT INTO holdings (id, symbol, name, quantity, average_cost, created_at) VALUES (:id, :symbol, :name, :quantity, :average_cost, :created_at)", item)
        return item

    def list_drafts(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM holding_drafts ORDER BY created_at DESC").fetchall()
        return [self._draft_dict(row) for row in rows]

    @staticmethod
    def _draft_dict(row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["client_row_id"] = str(item.get("client_row_id") or item["id"])
        item["candidates"] = json.loads(str(item.pop("candidates_json", "[]")))
        return item

    def add_draft(
        self, draft_id: str, client_row_id: str, name: str, quantity: float,
        average_cost: float, ocr_confidence: float | None = None,
    ) -> dict[str, object]:
        item = {
            "id": draft_id, "client_row_id": client_row_id, "name": name, "quantity": quantity,
            "average_cost": average_cost, "created_at": beijing_now().isoformat(),
            "ocr_confidence": ocr_confidence, "candidates_json": "[]", "candidates": [],
            "lookup_status": "pending", "lookup_message": "等待后台查询证券代码", "lookup_updated_at": None,
        }
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO holding_drafts
                (id, client_row_id, name, quantity, average_cost, ocr_confidence, created_at,
                 lookup_status, lookup_message, lookup_updated_at, candidates_json)
                VALUES (:id, :client_row_id, :name, :quantity, :average_cost, :ocr_confidence, :created_at,
                        :lookup_status, :lookup_message, :lookup_updated_at, :candidates_json)""",
                item,
            )
        return item

    def add_drafts(self, drafts: list[dict[str, object]]) -> list[dict[str, object]]:
        for draft in drafts:
            draft.setdefault("lookup_status", "pending")
            draft.setdefault("lookup_message", "等待后台查询证券代码")
            draft.setdefault("lookup_updated_at", None)
            draft.setdefault("ocr_confidence", None)
            draft.setdefault("candidates_json", "[]")
            draft.setdefault("candidates", [])
        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO holding_drafts
                (id, client_row_id, name, quantity, average_cost, ocr_confidence, created_at,
                 lookup_status, lookup_message, lookup_updated_at, candidates_json)
                VALUES (:id, :client_row_id, :name, :quantity, :average_cost, :ocr_confidence, :created_at,
                        :lookup_status, :lookup_message, :lookup_updated_at, :candidates_json)""",
                drafts,
            )
        return drafts

    def drafts_by_ids(self, draft_ids: list[str]) -> list[dict[str, object]]:
        if not draft_ids:
            return []
        placeholders = ",".join("?" for _ in draft_ids)
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM holding_drafts WHERE id IN ({placeholders})", draft_ids).fetchall()
        return [self._draft_dict(row) for row in rows]

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

    def set_draft_resolution(
        self, draft_id: str, lookup_status: str, lookup_message: str,
        candidates: list[dict[str, object]],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE holding_drafts
                SET lookup_status=?, lookup_message=?, lookup_updated_at=?, candidates_json=?
                WHERE id=?""",
                (
                    lookup_status, lookup_message, beijing_now().isoformat(),
                    json.dumps(candidates, ensure_ascii=False), draft_id,
                ),
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

    def confirm_draft(self, draft_id: str, holding_id: str, symbol: str, name: str) -> dict[str, object] | None:
        try:
            committed = self.commit_drafts([{"draft_id": draft_id, "symbol": symbol, "name": name}], [holding_id])
        except ValueError:
            return None
        return committed[0] if committed else None

    def commit_drafts(
        self, selections: list[dict[str, str]], holding_ids: list[str] | None = None,
    ) -> list[dict[str, object]]:
        draft_ids = [str(item["draft_id"]) for item in selections]
        submitted_draft_ids = list(draft_ids)
        symbols = [str(item["symbol"]).strip().upper() for item in selections]
        if len(draft_ids) != len(set(draft_ids)):
            raise ValueError("同一草稿不能重复提交")
        # A later screenshot row supersedes an earlier row for the same symbol.
        # This mirrors broker snapshots and prevents duplicate holdings.
        latest_indexes = {symbol: index for index, symbol in enumerate(symbols)}
        if len(latest_indexes) != len(symbols):
            retained = [index for index, symbol in enumerate(symbols) if latest_indexes[symbol] == index]
            selections = [selections[index] for index in retained]
            draft_ids = [draft_ids[index] for index in retained]
            symbols = [symbols[index] for index in retained]
        if len(symbols) != len(set(symbols)):
            raise ValueError("一次导入中不能把多行映射到同一个证券代码")
        generated_ids = holding_ids or [f"holding-{draft_id}" for draft_id in draft_ids]
        committed: list[dict[str, object]] = []
        now = beijing_now().isoformat()
        placeholders = ",".join("?" for _ in draft_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM holding_drafts WHERE id IN ({placeholders})", draft_ids
            ).fetchall()
            drafts_by_id = {str(row["id"]): row for row in rows}
            missing = [draft_id for draft_id in draft_ids if draft_id not in drafts_by_id]
            if missing:
                raise ValueError("部分草稿已不存在，请刷新后重试")
            for selection, holding_id, symbol in zip(selections, generated_ids, symbols):
                draft = drafts_by_id[str(selection["draft_id"])]
                item = {
                    "id": holding_id, "symbol": symbol, "name": str(selection["name"]),
                    "quantity": float(draft["quantity"]), "average_cost": float(draft["average_cost"]),
                    "created_at": now,
                }
                existing = connection.execute(
                    "SELECT id FROM holdings WHERE symbol = ? ORDER BY created_at DESC LIMIT 1", (symbol,)
                ).fetchone()
                if existing:
                    item["id"] = str(existing["id"])
                    connection.execute(
                        "UPDATE holdings SET name=:name, quantity=:quantity, average_cost=:average_cost, created_at=:created_at WHERE id=:id",
                        item,
                    )
                else:
                    connection.execute(
                        "INSERT INTO holdings (id, symbol, name, quantity, average_cost, created_at) VALUES (:id, :symbol, :name, :quantity, :average_cost, :created_at)",
                        item,
                    )
                committed.append(item)
            submitted_placeholders = ",".join("?" for _ in submitted_draft_ids)
            connection.execute(f"DELETE FROM holding_drafts WHERE id IN ({submitted_placeholders})", submitted_draft_ids)
        return committed

    def delete(self, holding_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
        return result.rowcount > 0

    def update(self, holding_id: str, symbol: str, name: str, quantity: float, average_cost: float) -> dict[str, object] | None:
        with self._connect() as connection:
            current = connection.execute("SELECT id, created_at FROM holdings WHERE id = ?", (holding_id,)).fetchone()
            if not current: return None
            duplicate = connection.execute("SELECT id FROM holdings WHERE symbol = ? AND id != ?", (symbol, holding_id)).fetchone()
            if duplicate:
                connection.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
                holding_id = str(duplicate["id"])
                current = connection.execute("SELECT id, created_at FROM holdings WHERE id = ?", (holding_id,)).fetchone()
            item = {"id": holding_id, "symbol": symbol, "name": name, "quantity": quantity, "average_cost": average_cost, "created_at": str(current["created_at"])}
            connection.execute("UPDATE holdings SET symbol=:symbol,name=:name,quantity=:quantity,average_cost=:average_cost WHERE id=:id", item)
        return item

    def delete_draft(self, draft_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM holding_drafts WHERE id = ?", (draft_id,))
        return result.rowcount > 0

    def clear_for_test(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM holdings")
            connection.execute("DELETE FROM watchlist")
            connection.execute("DELETE FROM holding_drafts")
            connection.execute("DELETE FROM market_quote_cache")
            connection.execute("DELETE FROM market_intelligence_cache")
            connection.execute("DELETE FROM symbol_lookup_cache")
            connection.execute("DELETE FROM personal_rules")
            connection.execute("DELETE FROM trade_plans")
            connection.execute("DELETE FROM learning_cases")
            connection.execute("DELETE FROM risk_cache")
            connection.execute("DELETE FROM daily_price_cache")
            connection.execute("DELETE FROM intraday_price_cache")
            connection.execute("DELETE FROM portfolio_analysis_cache")
            connection.execute("DELETE FROM analysis_runs")
            connection.execute("DELETE FROM sale_records")
            connection.execute("DELETE FROM ai_jobs")
            connection.execute("DELETE FROM account_cash")
            connection.execute("DELETE FROM ai_analysis_cache")
            connection.execute("DELETE FROM ai_analysis_cache_v2")
            connection.execute("DELETE FROM content_cache")
            connection.execute("DELETE FROM glossary_entries")
            connection.execute("DELETE FROM glossary_lookup_history")
            connection.execute("DELETE FROM decision_contexts")
            connection.execute("DELETE FROM decision_shadow_reports")
            connection.execute("DELETE FROM decision_ai_runs")
            connection.execute("DELETE FROM decision_reports")
            connection.execute("DELETE FROM feedback_events")
            connection.execute("DELETE FROM decision_jobs")
            connection.execute("DELETE FROM simulation_runs")
            connection.execute("DELETE FROM simulation_run_stages")
            connection.execute("DELETE FROM simulation_run_symbols")
            connection.execute("DELETE FROM daily_history_provider_attempts")
            connection.execute("DELETE FROM data_provider_health")

    def admin_summary(self) -> dict[str, int]:
        """Return only aggregate, non-sensitive operational counters for the admin console."""
        with self._connect() as connection:
            counts = {
                "holdings_count": connection.execute("SELECT COUNT(*) FROM holdings").fetchone()[0],
                "draft_count": connection.execute("SELECT COUNT(*) FROM holding_drafts").fetchone()[0],
                "pending_draft_count": connection.execute(
                    "SELECT COUNT(*) FROM holding_drafts WHERE lookup_status IN ('pending', 'querying', 'needs_review')"
                ).fetchone()[0],
                "cached_quotes_count": connection.execute("SELECT COUNT(*) FROM market_quote_cache").fetchone()[0],
                "market_history_count": connection.execute("SELECT COUNT(*) FROM market_quote_history").fetchone()[0],
                "cached_content_count": connection.execute("SELECT COUNT(*) FROM content_cache").fetchone()[0],
            }
            latest_market = connection.execute("SELECT MAX(recorded_at) FROM market_quote_history").fetchone()[0]
            counts["latest_market_at"] = latest_market
        counts["database_bytes"] = self.database_path.stat().st_size if self.database_path.exists() else 0
        return {key: int(value) for key, value in counts.items() if key != "latest_market_at"} | {"latest_market_at": counts["latest_market_at"]}

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
            connection.executemany(
                "INSERT INTO market_quote_history (symbol, payload, recorded_at) VALUES (?, ?, ?)",
                rows,
            )

    def system_settings(self) -> dict[str, object]:
        with self._connect() as connection:
            rows = connection.execute("SELECT setting_key, setting_value FROM system_settings").fetchall()
        stored = {str(row["setting_key"]): str(row["setting_value"]) for row in rows}
        interval = int(stored.get("paper_trading_interval_seconds", "600")) if stored.get("paper_trading_interval_seconds", "").isdigit() else 600
        return {"update_check_enabled": stored.get("update_check_enabled", "true").lower() == "true", "paper_trading_enabled": stored.get("paper_trading_enabled", "false").lower() == "true", "paper_trading_interval_seconds": max(300, interval)}

    def save_system_settings(self, settings: dict[str, object]) -> dict[str, object]:
        timestamp = beijing_now().isoformat()
        rows = [(key, "true" if value else "false", timestamp) if isinstance(value, bool) else (key, str(value), timestamp) for key, value in settings.items()]
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO system_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=excluded.updated_at",
                rows,
            )
        return self.system_settings()

    def migrate_paper_trading_default_interval(self, interval_seconds: int = 600) -> None:
        """Apply the product's 10-minute default once to existing local ledgers."""
        with self._connect() as connection:
            migrated = connection.execute(
                "SELECT 1 FROM system_settings WHERE setting_key='paper_trading_interval_default_migrated_v2'"
            ).fetchone()
            if migrated:
                return
            now = beijing_now().isoformat()
            connection.execute(
                "INSERT INTO system_settings (setting_key, setting_value, updated_at) VALUES ('paper_trading_interval_seconds', ?, ?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=excluded.updated_at",
                (str(max(300, interval_seconds)), now),
            )
            connection.execute(
                "INSERT INTO system_settings (setting_key, setting_value, updated_at) VALUES ('paper_trading_interval_default_migrated_v2', 'true', ?)",
                (now,),
            )

    def cached_analysis(self, cache_key: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM ai_analysis_cache_v2 WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def save_analysis(
        self,
        *,
        cache_key: str,
        content_id: str,
        content_hash: str,
        input_hash: str,
        rules_hash: str,
        user_context_hash: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        payload: dict[str, object],
        metadata: dict[str, object],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO ai_analysis_cache_v2
                (cache_key, content_id, content_hash, input_hash, rules_hash, user_context_hash,
                 model, prompt_version, schema_version, payload, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload=excluded.payload,
                    metadata=excluded.metadata,
                    created_at=excluded.created_at""",
                (
                    cache_key,
                    content_id,
                    content_hash,
                    input_hash,
                    rules_hash,
                    user_context_hash,
                    model,
                    prompt_version,
                    schema_version,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    json.dumps(metadata, ensure_ascii=False, default=str),
                    beijing_now().isoformat(),
                ),
            )

    def save_content(self, items: list[dict[str, object]]) -> None:
        timestamp = beijing_now().isoformat()
        rows = [(str(item["id"]), json.dumps(item, ensure_ascii=False, default=str), timestamp) for item in items]
        with self._connect() as connection:
            connection.executemany("INSERT INTO content_cache (content_id, payload, updated_at) VALUES (?, ?, ?) ON CONFLICT(content_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", rows)

    def cached_content(self, symbols: list[str] | None = None, limit: int = 80, offset: int = 0) -> list[dict[str, object]]:
        """Return source-linked content retained locally for evidence assembly."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM content_cache ORDER BY updated_at DESC LIMIT ? OFFSET ?", (max(1, limit), max(0, offset))
            ).fetchall()
        requested = {str(symbol).strip().upper() for symbol in (symbols or [])}
        items = [json.loads(str(row["payload"])) for row in rows]
        if not requested:
            return items
        return [item for item in items if requested.intersection({str(value).strip().upper() for value in item.get("related_symbols", [])})]

    def save_risk(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO risk_cache (symbol, payload, updated_at) VALUES (?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (str(item["symbol"]), json.dumps(item, ensure_ascii=False, default=str), beijing_now().isoformat()))

    def save_portfolio_analysis(self, payload: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO portfolio_analysis_cache (analysis_key, payload, updated_at) VALUES ('current', ?, ?) ON CONFLICT(analysis_key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (json.dumps(payload, ensure_ascii=False, default=str), beijing_now().isoformat()))

    def cached_portfolio_analysis(self) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM portfolio_analysis_cache WHERE analysis_key='current'"
            ).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def save_decision_context(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO decision_contexts (context_id, symbol, input_hash, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(item["context_id"]), str(item["symbol"]), str(item["input_hash"]),
                 json.dumps(item, ensure_ascii=False, default=str), str(item["generated_at"])),
            )
        self.capture_decision_lineage(item)

    def capture_decision_lineage(self, context: dict[str, object]) -> None:
        """Append immutable source snapshots and P1 shadow features for one context."""
        now = beijing_now().isoformat()
        symbol, context_id = str(context["symbol"]), str(context["context_id"])
        snapshots: dict[str, str] = {}
        sections = (("quote", "quote", context.get("quote")), ("daily_bars", "daily_bars", context.get("daily_bars")),
                    ("risk", "risk", context.get("risk")), ("market_intelligence", "market", context.get("market_regime")))
        with self._connect() as connection:
            quality = context.get("data_quality") or {}
            for field in [*(quality.get("missing_fields") or ()), *(quality.get("stale_fields") or ())]:
                connection.execute("INSERT INTO data_quality_events VALUES (?,?,?,?,?,?,?)", (str(uuid4()), symbol, "decision_context", "input_unavailable", "warning", now, json.dumps({"field": field, "context_id": context_id})))
            for source_key, data_class, payload in sections:
                if payload is None:
                    continue
                connection.execute("INSERT OR IGNORE INTO data_source_registry VALUES (?,?,?,?,?,?,?)", (source_key, source_key, data_class, 365, "append_only", 1, now))
                encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
                digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                snapshot_id = str(uuid4())
                available_at = str((payload or {}).get("retrieved_at") or (payload or {}).get("as_of") or context["generated_at"])
                connection.execute("INSERT INTO raw_data_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?)", (snapshot_id, source_key, symbol, data_class, str((payload or {}).get("as_of") or "") or None, available_at, now, digest, encoded, None, now))
                snapshots[source_key] = snapshot_id
            technical = context.get("technical") or {}
            risk = context.get("risk") or {}
            market = context.get("market_regime") or {}
            features = {
                "trend.price_above_sma20": technical.get("trend") == "up",
                "trend.sma20_above_sma60": (technical.get("sma20") or 0) >= (technical.get("sma60") or float("inf")),
                "momentum.rsi14": technical.get("rsi14"), "momentum.macd_histogram": technical.get("macd_histogram"),
                "volatility.atr_percent": technical.get("atr_percent"),
                "risk.historical_downside_probability": risk.get("historical_downside_probability"),
                "risk.annualized_volatility_percent": risk.get("annualized_volatility_percent"), "market.regime": market.get("regime"),
            }
            for key, value in features.items():
                connection.execute("INSERT OR IGNORE INTO feature_catalog VALUES (?,?,?,?,?)", (key, "v1", json.dumps({"key": key, "mode": "shadow"}), 0, now))
                connection.execute("INSERT OR REPLACE INTO feature_values VALUES (?,?,?,?,?,?,?,?,?)", (context_id, key, "v1", json.dumps(value), json.dumps(list(snapshots.values())), str(context["generated_at"]), str(context["generated_at"]), "available" if value is not None else "unavailable", now))

    def decision_lineage(self, decision_id: str) -> dict[str, object] | None:
        report = self.decision_report(decision_id)
        if not report:
            return None
        context_id = str(report["context_id"])
        with self._connect() as connection:
            rows = connection.execute("SELECT feature_key,feature_version,value_json,source_snapshot_ids,effective_at,available_at,quality_status FROM feature_values WHERE context_id=? ORDER BY feature_key", (context_id,)).fetchall()
            source_ids = {item for row in rows for item in json.loads(str(row["source_snapshot_ids"]))}
            snapshots = [dict(row) for row in connection.execute("SELECT snapshot_id,source_key,data_class,effective_at,available_at,payload_hash FROM raw_data_snapshots WHERE snapshot_id IN (%s)" % ",".join("?" for _ in source_ids), tuple(source_ids)).fetchall()] if source_ids else []
        return {"decision_id": decision_id, "context_id": context_id, "features": [{**dict(row), "value": json.loads(str(row["value_json"])), "source_snapshot_ids": json.loads(str(row["source_snapshot_ids"]))} for row in rows], "snapshots": snapshots}

    def save_research_report(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO research_reports VALUES (?,?,?,?,?,?)", (str(item["report_id"]), str(item["context_id"]), str(item["symbol"]), str(item["input_hash"]), json.dumps(item, ensure_ascii=False, default=str), str(item["generated_at"])))

    def research_report(self, report_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM research_reports WHERE report_id=?", (report_id,)).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def research_reports(self, symbol: str, limit: int = 20) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM research_reports WHERE symbol=? ORDER BY created_at DESC LIMIT ?", (symbol.strip().upper(), max(1, min(limit, 100)))).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def save_research_thesis(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO research_thesis_versions VALUES (?,?,?,?,?,?,?)",
                (str(item["thesis_id"]), int(item["version"]), str(item["symbol"]), str(item["report_id"]),
                 item.get("prior_version_id"), json.dumps(item, ensure_ascii=False, default=str), str(item["created_at"])),
            )

    def research_thesis(self, thesis_id: str, version: int | None = None) -> dict[str, object] | None:
        query = "SELECT payload FROM research_thesis_versions WHERE thesis_id=?"
        params: list[object] = [thesis_id]
        if version is not None:
            query += " AND version=?"; params.append(version)
        query += " ORDER BY version DESC LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def research_theses(self, symbol: str, limit: int = 20) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM research_thesis_versions WHERE symbol=? ORDER BY created_at DESC LIMIT ?",
                (symbol.strip().upper(), max(1, min(limit, 100))),
            ).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def data_quality_events(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        query, params = "SELECT * FROM data_quality_events", []
        if symbol:
            query += " WHERE symbol=?"; params.append(symbol.strip().upper())
        query += " ORDER BY observed_at DESC LIMIT ?"; params.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "payload": json.loads(str(row["payload"]))} for row in rows]

    def decision_context(self, context_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM decision_contexts WHERE context_id=?", (context_id,)
            ).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def save_shadow_report(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO decision_shadow_reports (shadow_id, context_id, symbol, input_hash, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(item["shadow_id"]), str(item["context_id"]), str(item["symbol"]), str(item["input_hash"]),
                 json.dumps(item, ensure_ascii=False, default=str), str(item["generated_at"])),
            )

    def shadow_reports(self, symbol: str, limit: int = 20) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM decision_shadow_reports WHERE symbol=? ORDER BY created_at DESC LIMIT ?",
                (symbol.strip().upper(), max(1, limit)),
            ).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def all_cached_quotes(self, limit: int = 1000) -> list[dict[str, object]]:
        """All locally persisted market quotes; never triggers a provider request."""
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM market_quote_cache ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 5000)),)).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def cached_market_intelligence(self, cache_key: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM market_intelligence_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def save_market_intelligence(self, cache_key: str, payload: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO market_intelligence_cache (cache_key, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (cache_key, json.dumps(payload, ensure_ascii=False, default=str), beijing_now().isoformat()),
            )

    def opportunity_symbols(self, minimum_daily_bars: int = 60, limit: int = 200) -> list[str]:
        """Symbols eligible for local opportunity scanning.

        This is deliberately limited to instruments for which the service already
        has both a cached quote and enough daily history.  It must not claim to
        represent the whole market when the configured data provider has only
        populated a partial universe.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT daily.symbol
                   FROM daily_price_cache AS daily
                   INNER JOIN market_quote_cache AS quote ON quote.symbol = daily.symbol
                   GROUP BY daily.symbol
                   HAVING COUNT(*) >= ?
                   ORDER BY MAX(daily.trading_date) DESC, daily.symbol ASC
                   LIMIT ?""",
                (max(1, minimum_daily_bars), max(1, limit)),
            ).fetchall()
        return [str(row["symbol"]) for row in rows]

    def save_decision_ai_run(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO decision_ai_runs (run_id,context_id,input_hash,status,error_code,payload,metadata,created_at) VALUES (?,?,?,?,?,?,?,?)", (str(item["run_id"]), str(item["context_id"]), str(item["input_hash"]), str(item["status"]), item.get("error_code"), json.dumps(item.get("payload", {}), ensure_ascii=False), json.dumps(item.get("metadata", {}), ensure_ascii=False), str(item["created_at"])))

    def decision_ai_runs(self, context_id: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        """Read the safe model-runtime audit without exposing credentials or reasoning."""
        query = "SELECT run_id,context_id,input_hash,status,error_code,payload,metadata,created_at FROM decision_ai_runs"
        args: list[object] = []
        if context_id:
            query += " WHERE context_id=?"
            args.append(str(context_id))
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, limit))
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [{
            **dict(row),
            "payload": json.loads(str(row["payload"])),
            "metadata": json.loads(str(row["metadata"])),
        } for row in rows]

    def save_decision_report(self, item: dict[str, object]) -> None:
        if not self._is_valid_decision_report(item):
            raise ValueError("refusing to persist an incomplete decision report")
        with self._connect() as connection:
            connection.execute("INSERT INTO decision_reports VALUES (?,?,?,?,?,?)", (str(item["decision_id"]), str(item["context_id"]), str(item["symbol"]), str(item["input_hash"]), json.dumps(item, ensure_ascii=False, default=str), str(item["generated_at"])))

    def decision_reports(self, symbol: str, limit: int = 50) -> list[dict[str, object]]:
        with self._connect() as connection:
            self._purge_invalid_decision_reports(connection, symbol=symbol)
            rows = connection.execute("SELECT payload FROM decision_reports WHERE symbol=? ORDER BY created_at DESC LIMIT ?", (symbol.strip().upper(), max(1, limit))).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def decision_report(self, decision_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            self._purge_invalid_decision_reports(connection, decision_id=decision_id)
            row = connection.execute("SELECT payload FROM decision_reports WHERE decision_id=?", (decision_id,)).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def record_feedback_event(self, item: dict[str, object]) -> dict[str, object]:
        """Record an audit-only outcome review against one frozen decision.

        This method intentionally has no write path to policy configuration,
        sizing, or model routing. Feedback is an offline evaluation dataset until
        a separately governed calibration phase is approved.
        """
        decision_id = str(item.get("decision_id") or "").strip()
        user_action = str(item.get("user_action") or "").strip()
        if not decision_id or not user_action:
            raise ValueError("feedback_decision_id_and_user_action_required")
        actual_outcome = item.get("actual_outcome") or {}
        hypothetical_outcome = item.get("hypothetical_outcome") or {}
        if not isinstance(actual_outcome, dict) or not isinstance(hypothetical_outcome, dict):
            raise ValueError("feedback_outcomes_must_be_objects")
        now = beijing_now().isoformat()
        with self._connect() as connection:
            decision_row = connection.execute(
                "SELECT input_hash,payload FROM decision_reports WHERE decision_id=?", (decision_id,)
            ).fetchone()
            if not decision_row:
                raise ValueError("feedback_frozen_decision_not_found")
            execution_log_id = str(item.get("execution_log_id") or "").strip() or None
            execution = None
            if execution_log_id:
                execution = connection.execute(
                    "SELECT decision_id,executed_at,quantity,price FROM paper_trading_logs WHERE id=? AND status='executed'",
                    (execution_log_id,),
                ).fetchone()
                if not execution:
                    raise ValueError("feedback_execution_not_found")
                if str(execution["decision_id"] or "") != decision_id:
                    raise ValueError("feedback_execution_decision_mismatch")
            event = {
                "feedback_id": str(item.get("feedback_id") or uuid4()),
                "decision_id": decision_id,
                "decision_input_hash": str(decision_row["input_hash"]),
                "execution_log_id": execution_log_id,
                "user_action": user_action,
                "execution_time": item.get("execution_time") or (execution["executed_at"] if execution else None),
                "quantity": item.get("quantity") if item.get("quantity") is not None else (execution["quantity"] if execution else None),
                "price": item.get("price") if item.get("price") is not None else (execution["price"] if execution else None),
                "actual_outcome_json": json.dumps(actual_outcome, ensure_ascii=False, sort_keys=True),
                "hypothetical_outcome_json": json.dumps(hypothetical_outcome, ensure_ascii=False, sort_keys=True),
                "explicit_feedback": item.get("explicit_feedback"),
                "review_label": item.get("review_label"),
                "policy_version": str(item.get("policy_version") or "feedback-v1-audit-only-no-auto-tune"),
                "created_at": now,
            }
            connection.execute(
                "INSERT INTO feedback_events "
                "(feedback_id,decision_id,decision_input_hash,execution_log_id,user_action,execution_time,quantity,price,actual_outcome_json,hypothetical_outcome_json,explicit_feedback,review_label,policy_version,created_at) "
                "VALUES (:feedback_id,:decision_id,:decision_input_hash,:execution_log_id,:user_action,:execution_time,:quantity,:price,:actual_outcome_json,:hypothetical_outcome_json,:explicit_feedback,:review_label,:policy_version,:created_at)",
                event,
            )
        return {
            **event,
            "actual_outcome": actual_outcome,
            "hypothetical_outcome": hypothetical_outcome,
            "automatic_tuning": False,
        }

    def feedback_events(self, decision_id: str | None = None, limit: int = 200) -> list[dict[str, object]]:
        query = "SELECT * FROM feedback_events"
        args: list[object] = []
        if decision_id:
            query += " WHERE decision_id=?"
            args.append(str(decision_id))
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, limit))
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [{
            **dict(row),
            "actual_outcome": json.loads(str(row["actual_outcome_json"])),
            "hypothetical_outcome": json.loads(str(row["hypothetical_outcome_json"])),
            "automatic_tuning": False,
        } for row in rows]

    def feedback_evaluation_dataset(self, policy_version: str | None = None, limit: int = 10_000) -> list[dict[str, object]]:
        """Return immutable feedback labels for offline policy-version evaluation.

        The result is intentionally read-only. Callers may export it for an
        offline benchmark, but it cannot calibrate production policy in-process.
        """
        query = "SELECT * FROM feedback_events"
        args: list[object] = []
        if policy_version:
            query += " WHERE policy_version=?"
            args.append(str(policy_version))
        query += " ORDER BY policy_version, created_at, feedback_id LIMIT ?"
        args.append(max(1, limit))
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [{
            "feedback_id": row["feedback_id"],
            "decision_id": row["decision_id"],
            "decision_input_hash": row["decision_input_hash"],
            "execution_log_id": row["execution_log_id"],
            "user_action": row["user_action"],
            "actual_outcome": json.loads(str(row["actual_outcome_json"])),
            "hypothetical_outcome": json.loads(str(row["hypothetical_outcome_json"])),
            "review_label": row["review_label"],
            "policy_version": row["policy_version"],
            "automatic_tuning": False,
        } for row in rows]

    @staticmethod
    def _is_valid_decision_report(item: object) -> bool:
        if not isinstance(item, dict):
            return False
        root_collections = ("evidence", "action_candidates", "operation_items")
        if not all(isinstance(item.get(field), list) for field in root_collections):
            return False
        assessment = item.get("ai_assessment")
        if assessment is None:
            return True
        assessment_collections = (
            "supporting_evidence_ids",
            "opposing_evidence_ids",
            "missing_evidence",
            "reasoning_steps",
            "rule_suggestions",
        )
        return isinstance(assessment, dict) and all(isinstance(assessment.get(field), list) for field in assessment_collections)

    def _valid_decision_reports(self, rows: list[sqlite3.Row]) -> tuple[list[dict[str, object]], list[str]]:
        reports: list[dict[str, object]] = []
        invalid_ids: list[str] = []
        for row in rows:
            try:
                report = json.loads(str(row["payload"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                invalid_ids.append(str(row["decision_id"]))
                continue
            if self._is_valid_decision_report(report):
                reports.append(report)
            else:
                invalid_ids.append(str(row["decision_id"]))
        return reports, invalid_ids

    def _purge_invalid_decision_reports(
        self,
        connection: sqlite3.Connection,
        symbol: str | None = None,
        decision_id: str | None = None,
    ) -> None:
        if symbol is not None:
            rows = connection.execute(
                "SELECT decision_id, payload FROM decision_reports WHERE symbol=?",
                (symbol.strip().upper(),),
            ).fetchall()
        elif decision_id is not None:
            rows = connection.execute(
                "SELECT decision_id, payload FROM decision_reports WHERE decision_id=?",
                (decision_id,),
            ).fetchall()
        else:
            return
        _, invalid_ids = self._valid_decision_reports(rows)
        if invalid_ids:
            connection.executemany("DELETE FROM decision_reports WHERE decision_id=?", ((report_id,) for report_id in invalid_ids))

    def enqueue_decision_job(self, item: dict[str, object]) -> dict[str, object]:
        now = beijing_now().isoformat()
        with self._connect() as connection:
            existing = connection.execute("SELECT * FROM decision_jobs WHERE input_hash=?", (item["input_hash"],)).fetchone()
            if existing: return {**dict(existing), "is_new": False}
            connection.execute("INSERT INTO decision_jobs VALUES (?,?,?,?,? ,0,?,NULL,?,?)", (item["job_id"], item["context_id"], item["symbol"], item["input_hash"], "pending", json.dumps(item, ensure_ascii=False), now, now))
        return {**item, "status": "pending", "attempts": 0, "is_new": True}

    def decision_job(self, job_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM decision_jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def update_decision_job(self, job_id: str, status: str, error_message: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE decision_jobs SET status=?, attempts=attempts+1, error_message=?, updated_at=? WHERE job_id=?", (status, error_message, beijing_now().isoformat(), job_id))

    def cached_risk(self, symbol: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM risk_cache WHERE symbol = ?", (symbol,)).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def save_daily_prices(self, symbol: str, bars: list[dict[str, object]]) -> None:
        """Upsert normalized end-of-day bars; raw provider payloads are deliberately not retained."""
        if not bars:
            return
        now = beijing_now().isoformat()
        rows = [
            (symbol, str(bar["trading_date"]), decimal_text(bar.get("open")), decimal_text(bar["close"]), decimal_text(bar.get("high")), decimal_text(bar.get("low")),
             decimal_text(bar.get("volume")), decimal_text(bar.get("amount")), decimal_text(bar.get("amplitude_percent")), decimal_text(bar.get("change_percent")), decimal_text(bar.get("change_amount")), decimal_text(bar.get("turnover_rate")), str(bar.get("adjustment", "qfq")),
             str(bar.get("source", "public-market-data")), now)
            for bar in bars
        ]
        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO daily_price_cache
                (symbol, trading_date, open, close, high, low, volume, amount, amplitude_percent, change_percent, change_amount, turnover_rate, adjustment, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trading_date) DO UPDATE SET
                    open=excluded.open, close=excluded.close, high=excluded.high, low=excluded.low,
                    volume=excluded.volume, amount=excluded.amount, amplitude_percent=excluded.amplitude_percent,
                    change_percent=excluded.change_percent, change_amount=excluded.change_amount, turnover_rate=excluded.turnover_rate, adjustment=excluded.adjustment,
                    source=excluded.source, updated_at=excluded.updated_at""",
                rows,
            )

    def replace_daily_prices(self, symbol: str, bars: list[dict[str, object]]) -> None:
        """Atomically replace one symbol's daily cache after a full provider refresh."""
        if not bars:
            return
        normalized_symbol = symbol.strip().upper()
        now = beijing_now().isoformat()
        rows = [
            (normalized_symbol, str(bar["trading_date"]), decimal_text(bar.get("open")), decimal_text(bar["close"]), decimal_text(bar.get("high")), decimal_text(bar.get("low")),
             decimal_text(bar.get("volume")), decimal_text(bar.get("amount")), decimal_text(bar.get("amplitude_percent")), decimal_text(bar.get("change_percent")), decimal_text(bar.get("change_amount")), decimal_text(bar.get("turnover_rate")), str(bar.get("adjustment", "qfq")),
             str(bar.get("source", "public-market-data")), now)
            for bar in bars
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM daily_price_cache WHERE symbol=?", (normalized_symbol,))
            connection.executemany(
                """INSERT INTO daily_price_cache
                (symbol, trading_date, open, close, high, low, volume, amount, amplitude_percent, change_percent, change_amount, turnover_rate, adjustment, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )

    def delete_daily_prices(self, symbol: str) -> int:
        """Remove cached daily bars for a symbol so corrupted data cannot reach analysis."""
        with self._connect() as connection:
            result = connection.execute("DELETE FROM daily_price_cache WHERE symbol=?", (symbol.strip().upper(),))
        return result.rowcount

    def daily_prices(self, symbol: str, limit: int = 800) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT trading_date, open, close, high, low, volume, amount, amplitude_percent, change_percent, change_amount, turnover_rate, adjustment, source FROM daily_price_cache "
                "WHERE symbol=? AND length(trading_date)=10 AND substr(trading_date, 5, 1)='-' "
                "AND substr(trading_date, 8, 1)='-' ORDER BY trading_date DESC LIMIT ?", (symbol, max(1, limit)),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def daily_prices_between(self, symbol: str, start_date: str, end_date: str, limit: int = 2000) -> list[dict[str, object]]:
        """Read one inclusive daily-history range from the local cache only."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT trading_date, open, close, high, low, volume, amount, amplitude_percent, change_percent, change_amount, turnover_rate, adjustment, source FROM daily_price_cache "
                "WHERE symbol=? AND trading_date>=? AND trading_date<=? ORDER BY trading_date ASC LIMIT ?",
                (symbol.strip().upper(), start_date, end_date, max(1, limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_instrument_metadata(self, item: dict[str, object]) -> dict[str, object]:
        now = beijing_now().isoformat()
        payload = {**item, "symbol": str(item["symbol"]).strip().upper(), "updated_at": now}
        with self._connect() as connection:
            connection.execute("""INSERT INTO instrument_metadata
                (symbol, market, currency, lot_size, price_tick, source, as_of, updated_at)
                VALUES (:symbol, :market, :currency, :lot_size, :price_tick, :source, :as_of, :updated_at)
                ON CONFLICT(symbol) DO UPDATE SET market=excluded.market, currency=excluded.currency,
                lot_size=excluded.lot_size, price_tick=excluded.price_tick, source=excluded.source,
                as_of=excluded.as_of, updated_at=excluded.updated_at""", payload)
        return payload

    def instrument_metadata(self, symbol: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM instrument_metadata WHERE symbol=?", (symbol.strip().upper(),)).fetchone()
        return dict(row) if row else None

    def add_learning_case(self, item: dict[str, object]) -> dict[str, object]:
        with self._connect() as connection:
            item["evidence_links"] = json.dumps(item.get("evidence_links", []), ensure_ascii=False)
            connection.execute("INSERT INTO learning_cases (id, symbol, title, context, lesson, outcome, position_band, planned_action, confidence, evidence_links, created_at) VALUES (:id,:symbol,:title,:context,:lesson,:outcome,:position_band,:planned_action,:confidence,:evidence_links,:created_at)", item)
        return {**item, "evidence_links": json.loads(str(item["evidence_links"]))}

    def learning_cases(self, symbol: str | None = None) -> list[dict[str, object]]:
        query, params = ("SELECT * FROM learning_cases WHERE symbol=? OR symbol IS NULL ORDER BY created_at DESC", [symbol]) if symbol else ("SELECT * FROM learning_cases ORDER BY created_at DESC", [])
        with self._connect() as connection: rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "evidence_links": json.loads(str(row["evidence_links"]))} for row in rows]

    def update_learning_case(self, case_id: str, item: dict[str, object]) -> dict[str, object] | None:
        """Update the editable content while retaining the original review timestamp."""
        payload = {**item, "evidence_links": json.dumps(item.get("evidence_links", []), ensure_ascii=False)}
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE learning_cases SET symbol=:symbol, title=:title, context=:context,
                lesson=:lesson, outcome=:outcome, position_band=:position_band,
                planned_action=:planned_action, confidence=:confidence, evidence_links=:evidence_links
                WHERE id=:id""",
                {**payload, "id": case_id},
            )
        if cursor.rowcount == 0:
            return None
        return {"id": case_id, **item, "created_at": self.learning_case_created_at(case_id)}

    def learning_case_created_at(self, case_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute("SELECT created_at FROM learning_cases WHERE id=?", (case_id,)).fetchone()
        return str(row["created_at"]) if row else ""

    def delete_learning_case(self, case_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM learning_cases WHERE id=?", (case_id,))
        return cursor.rowcount > 0

    def research_rules(self) -> list[dict[str, object]]:
        with self._connect() as connection: rows = connection.execute("SELECT * FROM research_rules ORDER BY category, id").fetchall()
        return [dict(row) for row in rows]

    def save_intraday_prices(self, symbol: str, bars: list[dict[str, object]]) -> None:
        if not bars:
            return
        now = beijing_now().isoformat()
        rows = []
        for bar in bars:
            try:
                ohlc = [float(bar[field]) for field in ("open", "close", "high", "low")]
            except (KeyError, TypeError, ValueError):
                continue
            if not all(math.isfinite(value) for value in ohlc):
                continue
            rows.append((
                symbol, str(bar["bar_time"]), *ohlc,
                bar.get("volume"), bar.get("amount"), bar.get("average_price"), str(bar.get("source", "AKShare intraday")), now,
            ))
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany("INSERT OR REPLACE INTO intraday_price_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    def record_broker_settlement_receipt(self, item: dict[str, object]) -> dict[str, object]:
        """Persist an exact broker settlement fact without inferring a fee rule.

        This is deliberately audit-only. A receipt can establish what a specific
        Stock Connect fill settled for in CNY, including the broker's actual fee
        breakdown, but it cannot by itself authorize a new paper trade.
        """
        symbol = str(item.get("symbol") or "").strip().upper()
        market = str(item.get("market") or "").strip().upper()
        side = str(item.get("side") or "").strip().upper()
        trade_currency = str(item.get("trade_currency") or "").strip().upper()
        settlement_currency = str(item.get("settlement_currency") or "").strip().upper()
        broker = str(item.get("broker") or "").strip()
        occurred_at = str(item.get("occurred_at") or "").strip()
        try:
            quantity = float(item.get("quantity"))
            trade_price = float(item.get("trade_price"))
            gross_settlement_amount = float(item.get("gross_settlement_amount"))
            total_fee = float(item.get("total_fee"))
            net_settlement_amount = float(item.get("net_settlement_amount"))
        except (TypeError, ValueError) as error:
            raise ValueError("broker_receipt_amount_invalid") from error
        if not symbol or market not in {"CN", "HK", "US"} or side not in {"BUY", "SELL"}:
            raise ValueError("broker_receipt_identity_invalid")
        if not trade_currency or not settlement_currency or not broker or not occurred_at:
            raise ValueError("broker_receipt_identity_missing")
        if not all(math.isfinite(value) and value >= 0 for value in (quantity, trade_price, gross_settlement_amount, total_fee, net_settlement_amount)):
            raise ValueError("broker_receipt_amount_invalid")
        if quantity <= 0 or trade_price <= 0 or gross_settlement_amount <= 0:
            raise ValueError("broker_receipt_amount_invalid")
        expected_net = gross_settlement_amount + total_fee if side == "BUY" else gross_settlement_amount - total_fee
        if not math.isclose(net_settlement_amount, expected_net, abs_tol=.02):
            raise ValueError("broker_receipt_net_settlement_mismatch")
        breakdown: dict[str, float | None] = {}
        for field in ("commission", "stamp_duty", "other_fee"):
            value = item.get(field)
            if value is None:
                breakdown[field] = None
                continue
            try:
                number = float(value)
            except (TypeError, ValueError) as error:
                raise ValueError("broker_receipt_fee_invalid") from error
            if not math.isfinite(number) or number < 0:
                raise ValueError("broker_receipt_fee_invalid")
            breakdown[field] = number
        known_fees = [value for value in breakdown.values() if value is not None]
        if len(known_fees) == 3 and not math.isclose(sum(known_fees), total_fee, abs_tol=.02):
            raise ValueError("broker_receipt_fee_breakdown_mismatch")
        implied_fx_rate = gross_settlement_amount / (quantity * trade_price)
        receipt = {
            "receipt_id": str(item.get("receipt_id") or uuid4()),
            "decision_id": str(item.get("decision_id") or "") or None,
            "symbol": symbol, "market": market, "side": side,
            "quantity": quantity, "trade_price": trade_price,
            "trade_currency": trade_currency, "settlement_currency": settlement_currency,
            "gross_settlement_amount": gross_settlement_amount,
            **breakdown,
            "total_fee": total_fee, "net_settlement_amount": net_settlement_amount,
            "implied_fx_rate": implied_fx_rate, "broker": broker,
            "occurred_at": occurred_at,
            "source_reference": str(item.get("source_reference") or "") or None,
            "created_at": beijing_now().isoformat(),
        }
        receipt["payload"] = json.dumps(receipt, ensure_ascii=False, sort_keys=True, default=str)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO broker_settlement_receipts "
                "(receipt_id,decision_id,symbol,market,side,quantity,trade_price,trade_currency,settlement_currency,"
                "gross_settlement_amount,commission,stamp_duty,other_fee,total_fee,net_settlement_amount,"
                "implied_fx_rate,broker,occurred_at,source_reference,payload,created_at) "
                "VALUES (:receipt_id,:decision_id,:symbol,:market,:side,:quantity,:trade_price,:trade_currency,"
                ":settlement_currency,:gross_settlement_amount,:commission,:stamp_duty,:other_fee,:total_fee,"
                ":net_settlement_amount,:implied_fx_rate,:broker,:occurred_at,:source_reference,:payload,:created_at)",
                receipt,
            )
        receipt.pop("payload")
        return receipt

    def broker_settlement_receipts(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        query = "SELECT * FROM broker_settlement_receipts"
        args: list[object] = []
        if symbol:
            query += " WHERE symbol=?"
            args.append(str(symbol).strip().upper())
        query += " ORDER BY occurred_at DESC LIMIT ?"
        args.append(max(1, limit))
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [{key: value for key, value in dict(row).items() if key != "payload"} for row in rows]

    def intraday_prices(self, symbol: str, limit: int = 500) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT bar_time,open,close,high,low,volume,amount,average_price,source,updated_at FROM intraday_price_cache WHERE symbol=? ORDER BY bar_time DESC LIMIT ?", (symbol, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def save_glossary_entry(self, item: dict[str, object]) -> dict[str, object]:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO glossary_entries (term_key,term,plain_explanation,watch_for,source,updated_at)
                VALUES (:term_key,:term,:plain_explanation,:watch_for,:source,:updated_at)
                ON CONFLICT(term_key) DO UPDATE SET term=excluded.term,
                plain_explanation=excluded.plain_explanation, watch_for=excluded.watch_for,
                source=excluded.source, updated_at=excluded.updated_at""",
                item,
            )
        return item

    def watchlist(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM watchlist ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def save_watchlist_item(self, symbol: str, name: str) -> dict[str, object]:
        now = beijing_now().isoformat()
        item = {"symbol": symbol.strip().upper(), "name": name.strip(), "created_at": now, "updated_at": now}
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO watchlist (symbol, name, created_at, updated_at)
                VALUES (:symbol, :name, :created_at, :updated_at)
                ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at""",
                item,
            )
            row = connection.execute("SELECT * FROM watchlist WHERE symbol=?", (item["symbol"],)).fetchone()
        return dict(row)

    def delete_watchlist_item(self, symbol: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM watchlist WHERE symbol=?", (symbol.strip().upper(),))
        return result.rowcount > 0

    def glossary_entry(self, term_key: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM glossary_entries WHERE term_key = ?", (term_key,)).fetchone()
        return dict(row) if row else None

    def glossary_entries(self, limit: int = 500) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT term,plain_explanation,watch_for,source FROM glossary_entries ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def record_glossary_lookup(self, term_key: str, term: str, context: str, found: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO glossary_lookup_history (term_key,term,context,found,looked_up_at)
                VALUES (?, ?, ?, ?, ?)""",
                (term_key, term, context, int(found), beijing_now().isoformat()),
            )

    def personal_rules(self) -> list[dict[str, object]]:
        with self._connect() as connection: rows = connection.execute("SELECT * FROM personal_rules ORDER BY scope, symbol").fetchall()
        return [dict(row) for row in rows]

    def save_personal_rule(self, item: dict[str, object]) -> dict[str, object]:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id, version FROM personal_rules WHERE scope = ? AND COALESCE(symbol, '') = COALESCE(?, '') ORDER BY updated_at DESC LIMIT 1",
                (item["scope"], item.get("symbol")),
            ).fetchone()
            if existing:
                item["id"] = str(existing["id"])
                item["version"] = int(existing["version"]) + 1
            connection.execute("INSERT INTO personal_rules (id,scope,symbol,max_position_percent,loss_review_percent,volatility_review_percent,enabled,version,updated_at) VALUES (:id,:scope,:symbol,:max_position_percent,:loss_review_percent,:volatility_review_percent,:enabled,:version,:updated_at) ON CONFLICT(id) DO UPDATE SET scope=excluded.scope,symbol=excluded.symbol,max_position_percent=excluded.max_position_percent,loss_review_percent=excluded.loss_review_percent,volatility_review_percent=excluded.volatility_review_percent,enabled=excluded.enabled,version=personal_rules.version+1,updated_at=excluded.updated_at", item)
        return item

    def sell_holding(self, holding_id: str, sale_id: str, quantity: float, sale_price: float, reason: str, analysis_snapshot: dict[str, object]) -> dict[str, object] | None:
        """Atomically record realized P/L and reduce (or close) the open holding."""
        with self._connect() as connection:
            holding = connection.execute("SELECT * FROM holdings WHERE id=?", (holding_id,)).fetchone()
            if not holding:
                return None
            available, cost = float(holding["quantity"]), float(holding["average_cost"])
            if quantity > available + 1e-9:
                raise ValueError("出售数量不能超过当前持仓数量")
            remaining = max(0.0, available - quantity)
            proceeds, cost_basis = quantity * sale_price, quantity * cost
            pnl = proceeds - cost_basis
            item = {"id": sale_id, "holding_id": holding_id, "symbol": str(holding["symbol"]), "name": str(holding["name"]), "quantity": quantity, "sale_price": sale_price, "average_cost": cost, "proceeds": proceeds, "cost_basis": cost_basis, "realized_pnl": pnl, "realized_pnl_percent": pnl / cost_basis * 100 if cost_basis else 0.0, "remaining_quantity": remaining, "reason": reason, "analysis_snapshot": analysis_snapshot, "sold_at": beijing_now().isoformat()}
            connection.execute("""INSERT INTO sale_records VALUES (:id,:holding_id,:symbol,:name,:quantity,:sale_price,:average_cost,:proceeds,:cost_basis,:realized_pnl,:realized_pnl_percent,:remaining_quantity,:reason,:analysis_snapshot,:sold_at)""", {**item, "analysis_snapshot": json.dumps(analysis_snapshot, ensure_ascii=False, default=str)})
            # A sale is one atomic account event: its proceeds must become
            # available cash in the very same transaction as the sale record.
            connection.execute(
                """INSERT INTO account_cash (account_id, available_cash, updated_at)
                VALUES ('default', ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    available_cash=account_cash.available_cash + excluded.available_cash,
                    updated_at=excluded.updated_at""",
                (proceeds, item["sold_at"]),
            )
            if remaining <= 1e-9:
                connection.execute("DELETE FROM holdings WHERE id=?", (holding_id,))
            else:
                connection.execute("UPDATE holdings SET quantity=? WHERE id=?", (remaining, holding_id))
        return item

    def sale_records(self, symbol: str | None = None, limit: int = 200) -> list[dict[str, object]]:
        query, params = (("SELECT * FROM sale_records WHERE symbol=? ORDER BY sold_at DESC LIMIT ?", [symbol, limit]) if symbol else ("SELECT * FROM sale_records ORDER BY sold_at DESC LIMIT ?", [limit]))
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "analysis_snapshot": json.loads(str(row["analysis_snapshot"]))} for row in rows]

    def research_targets(self) -> list[dict[str, object]]:
        """Return active holdings, independent watchlist items, and completed sales."""
        targets: dict[str, dict[str, object]] = {}
        for item in self.sale_records():
            if float(item["remaining_quantity"]) <= 1e-9:
                targets.setdefault(str(item["symbol"]), {
                    "symbol": item["symbol"], "name": item["name"], "status": "closed_position", "last_activity_at": item["sold_at"],
                })
        for item in self.watchlist():
            targets[str(item["symbol"])] = {
                "symbol": item["symbol"], "name": item["name"], "status": "watchlist", "last_activity_at": item["updated_at"],
            }
        for item in self.list():
            targets[str(item["symbol"])] = {
                "symbol": item["symbol"], "name": item["name"], "status": "active_holding", "last_activity_at": item["created_at"],
            }
        return sorted(targets.values(), key=lambda item: str(item["last_activity_at"]), reverse=True)

    def trade_plans(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM trade_plans ORDER BY updated_at DESC").fetchall()
        return [{**dict(row), "catalysts": json.loads(str(row["catalysts_json"])), "structured_conditions": json.loads(str(row["structured_conditions_json"])), "enabled": bool(row["enabled"])} for row in rows]

    def trade_plan(self, symbol: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM trade_plans WHERE symbol=?", (symbol,)).fetchone()
        return ({**dict(row), "catalysts": json.loads(str(row["catalysts_json"])), "structured_conditions": json.loads(str(row["structured_conditions_json"])), "enabled": bool(row["enabled"])} if row else None)

    def save_trade_plan(self, item: dict[str, object]) -> dict[str, object]:
        now = beijing_now().isoformat()
        item = {"benchmark_symbol": None, "benchmark_name": None, "invalidation_price": None, "version": 1, **item}
        item = {**item, "catalysts_json": json.dumps(item.get("catalysts", []), ensure_ascii=False), "structured_conditions_json": json.dumps(item.get("structured_conditions", []), ensure_ascii=False), "updated_at": now}
        with self._connect() as connection:
            existing = connection.execute("SELECT id, version FROM trade_plans WHERE symbol=?", (item["symbol"],)).fetchone()
            if existing:
                item["id"], item["version"] = str(existing["id"]), int(existing["version"]) + 1
            connection.execute(
                """INSERT INTO trade_plans
                (id,symbol,horizon,thesis,market_expectation,benchmark_symbol,benchmark_name,catalysts_json,structured_conditions_json,entry_condition,add_condition,reduce_condition,exit_condition,max_position_percent,risk_budget_percent,invalidation_price,enabled,version,updated_at)
                VALUES (:id,:symbol,:horizon,:thesis,:market_expectation,:benchmark_symbol,:benchmark_name,:catalysts_json,:structured_conditions_json,:entry_condition,:add_condition,:reduce_condition,:exit_condition,:max_position_percent,:risk_budget_percent,:invalidation_price,:enabled,:version,:updated_at)
                ON CONFLICT(symbol) DO UPDATE SET horizon=excluded.horizon,thesis=excluded.thesis,market_expectation=excluded.market_expectation,benchmark_symbol=excluded.benchmark_symbol,benchmark_name=excluded.benchmark_name,catalysts_json=excluded.catalysts_json,structured_conditions_json=excluded.structured_conditions_json,entry_condition=excluded.entry_condition,add_condition=excluded.add_condition,reduce_condition=excluded.reduce_condition,exit_condition=excluded.exit_condition,max_position_percent=excluded.max_position_percent,risk_budget_percent=excluded.risk_budget_percent,invalidation_price=excluded.invalidation_price,enabled=excluded.enabled,version=excluded.version,updated_at=excluded.updated_at""",
                item,
            )
        result = {**item, "catalysts": json.loads(str(item.pop("catalysts_json"))), "structured_conditions": json.loads(str(item.pop("structured_conditions_json"))), "enabled": bool(item["enabled"])}
        return result

    def save_analysis_run(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO analysis_runs (id, payload, created_at) VALUES (?, ?, ?)", (str(item["id"]), json.dumps(item, ensure_ascii=False, default=str), beijing_now().isoformat()))

    def save_daily_review(self, item: dict[str, object]) -> dict[str, object]:
        """Persist one immutable end-of-day plan with later execution and outcome updates."""
        now = beijing_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO daily_reviews (id, review_date, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(review_date) DO UPDATE SET id=excluded.id, payload=excluded.payload, updated_at=excluded.updated_at",
                (str(item["id"]), str(item["review_date"]), json.dumps(item, ensure_ascii=False, default=str), now, now),
            )
        return item

    def daily_reviews(self, limit: int = 60) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM daily_reviews ORDER BY review_date DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def daily_review(self, review_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM daily_reviews WHERE id=?", (review_id,)).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def available_cash(self) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute("SELECT available_cash, updated_at FROM account_cash WHERE account_id='default'").fetchone()
        return {"available_cash": float(row["available_cash"]) if row else 0.0, "updated_at": row["updated_at"] if row else beijing_now().isoformat()}

    def save_available_cash(self, available_cash: float) -> dict[str, object]:
        now = beijing_now().isoformat()
        with self._connect() as connection:
            existing = connection.execute("SELECT available_cash FROM account_cash WHERE account_id='default'").fetchone()
            previous = float(existing["available_cash"]) if existing else 0.0
            connection.execute("INSERT INTO account_cash VALUES ('default', ?, ?) ON CONFLICT(account_id) DO UPDATE SET available_cash=excluded.available_cash, updated_at=excluded.updated_at", (available_cash, now))
            delta = float(available_cash) - previous
            if abs(delta) > 1e-9:
                connection.execute(
                    "INSERT INTO paper_trading_cash_flows (id,amount,flow_type,note,occurred_at) VALUES (?,?,?,?,?)",
                    (str(uuid4()), delta, "deposit" if delta > 0 else "withdrawal", "管理员调整可用资金", now),
                )
        return {"available_cash": available_cash, "updated_at": now}

    def set_paper_net_contributions(self, amount: float) -> dict[str, object]:
        """Rebase legacy paper ledger capital without changing current cash or positions."""
        now = beijing_now().isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM paper_trading_cash_flows")
            if abs(amount) > 1e-9:
                connection.execute(
                    "INSERT INTO paper_trading_cash_flows (id,amount,flow_type,note,occurred_at) VALUES (?,?,?,?,?)",
                    (str(uuid4()), amount, "opening_balance", "历史账套累计净入金校准", now),
                )
        return self.paper_account()

    def paper_account(self) -> dict[str, object]:
        settings = self.system_settings()
        now = beijing_now()
        with self._connect() as connection:
            cash_row = connection.execute("SELECT available_cash, updated_at FROM account_cash WHERE account_id='default'").fetchone()
            row = connection.execute("SELECT initial_cash FROM paper_trading_accounts WHERE account_id='default'").fetchone()
            flow_row = connection.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM paper_trading_cash_flows").fetchone()
            positions = [dict(item) for item in connection.execute("SELECT * FROM paper_trading_positions ORDER BY updated_at DESC").fetchall()]
            lots = [dict(item) for item in connection.execute(
                "SELECT * FROM paper_position_lots WHERE quantity > 0"
            ).fetchall()]
            quotes = {str(item["symbol"]): json.loads(str(item["payload"])) for item in connection.execute("SELECT symbol,payload FROM market_quote_cache").fetchall()}
        lot_totals: dict[str, float] = {}
        next_sellable: dict[str, str] = {}
        for lot in lots:
            symbol = str(lot["symbol"])
            if self._lot_is_sellable(lot, now):
                lot_totals[symbol] = lot_totals.get(symbol, 0.0) + float(lot["quantity"])
                continue
            candidate = self._lot_next_sellable_at(lot)
            if candidate and (symbol not in next_sellable or candidate < next_sellable[symbol]):
                next_sellable[symbol] = candidate
        enriched_positions = []
        for position in positions:
            price = float((quotes.get(str(position["symbol"]), {}).get("price")) or position["average_cost"])
            market_value = float(position["quantity"]) * price
            cost_value = float(position["quantity"]) * float(position["average_cost"])
            sellable_quantity = min(float(position["quantity"]), lot_totals.get(str(position["symbol"]), 0.0))
            enriched_positions.append({
                **position,
                "sellable_quantity": sellable_quantity,
                "locked_quantity": max(0.0, float(position["quantity"]) - sellable_quantity),
                "next_eligible_sell_at": next_sellable.get(str(position["symbol"])),
                "last_price": price,
                "market_value": market_value,
                "unrealized_pnl": market_value - cost_value,
                "unrealized_return_percent": (market_value / cost_value - 1) * 100 if cost_value else 0.0,
            })
        positions = enriched_positions
        market_value = sum(float(position["market_value"]) for position in positions)
        cash = float(cash_row["available_cash"]) if cash_row else 0.0
        legacy_initial_cash = float(row["initial_cash"]) if row else 0.0
        net_contributions = float(flow_row["total"]) if flow_row else 0.0
        # Existing installations created before cash flows use their stored
        # opening balance until the user performs an explicit reconciliation.
        if abs(net_contributions) <= 1e-9:
            net_contributions = legacy_initial_cash
        equity = cash + market_value
        return {"available_cash": cash, "initial_cash": net_contributions, "net_contributions": net_contributions, "market_value": market_value, "total_equity": equity, "total_pnl": equity - net_contributions, "total_return_percent": (equity / net_contributions - 1) * 100 if net_contributions else 0.0, "updated_at": cash_row["updated_at"] if cash_row else beijing_now().isoformat(), "enabled": settings["paper_trading_enabled"], "positions": positions}

    def record_paper_equity_snapshot(self) -> dict[str, object]:
        account = self.paper_account()
        now = beijing_now().isoformat()
        with self._connect() as connection:
            connection.execute("INSERT INTO paper_trading_equity_snapshots (total_equity,available_cash,market_value,total_pnl,recorded_at) VALUES (?,?,?,?,?)", (account["total_equity"], account["available_cash"], account["market_value"], account["total_pnl"], now))
        return {"recorded_at": now, **{key: account[key] for key in ("total_equity", "available_cash", "market_value", "total_pnl")}}

    def paper_equity_snapshots(self, limit: int = 120) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT total_equity,available_cash,market_value,total_pnl,recorded_at FROM paper_trading_equity_snapshots ORDER BY recorded_at DESC LIMIT ?", (max(1, limit),)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def save_paper_account(self, available_cash: float) -> dict[str, object]:
        # Compatibility endpoint: paper trading now shares the one database cash ledger.
        self.save_available_cash(available_cash)
        return self.paper_account()

    def paper_logs(self, symbol: str | None = None, limit: int = 200) -> list[dict[str, object]]:
        query, args = ("SELECT * FROM paper_trading_logs WHERE symbol=? ORDER BY executed_at DESC LIMIT ?", [symbol, limit]) if symbol else ("SELECT * FROM paper_trading_logs ORDER BY executed_at DESC LIMIT ?", [limit])
        with self._connect() as connection: rows = connection.execute(query, args).fetchall()
        return [dict(row) for row in rows]

    def paper_position_lots(self, symbol: str | None = None) -> list[dict[str, object]]:
        """Expose immutable-ish acquisition lots and their current sellability."""
        query = (
            "SELECT * FROM paper_position_lots WHERE symbol=? ORDER BY acquired_at, lot_id"
            if symbol
            else "SELECT * FROM paper_position_lots ORDER BY acquired_at, lot_id"
        )
        args = [str(symbol).strip().upper()] if symbol else []
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        now = beijing_now()
        return [self._display_lot(dict(row), now) for row in rows]

    @staticmethod
    def _lot_next_sellable_at(lot: dict[str, object]) -> str | None:
        value = lot.get("sellable_at")
        return str(value) if value else None

    @staticmethod
    def _lot_is_sellable(lot: dict[str, object], now: datetime) -> bool:
        """Read sellability without mutating the ledger for an account GET."""
        if float(lot.get("quantity") or 0) <= 0:
            return False
        sellable_at = lot.get("sellable_at")
        if sellable_at:
            try:
                parsed = datetime.fromisoformat(str(sellable_at).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=now.tzinfo)
                return parsed <= now
            except ValueError:
                return False
        # Pre-0017 rows retain the former conservative calendar-date rule until
        # a later migration can materialize an exchange-calendar timestamp.
        return str(lot.get("market") or "").upper() != "CN" or str(lot.get("acquired_at") or "")[:10] < now.date().isoformat()

    def _display_lot(self, lot: dict[str, object], now: datetime) -> dict[str, object]:
        sellable = float(lot.get("quantity") or 0) if self._lot_is_sellable(lot, now) else 0.0
        return {
            **lot,
            "sellable_quantity": sellable,
            "settlement_state": "SETTLED" if sellable > 0 and str(lot.get("settlement_state")) == "PENDING_T1" else lot.get("settlement_state"),
        }

    @staticmethod
    def _new_lot_sellable_at(market: str, acquired_at: datetime) -> str | None:
        if market != "CN":
            return acquired_at.isoformat()
        from app.trading_calendar import TradingCalendarService
        next_open = TradingCalendarService().next_session_open(market, acquired_at)
        return next_open.isoformat() if next_open is not None else None

    def record_paper_skip(self, *, symbol: str, name: str, decision_id: str | None, reason: str, price: float = 0.0) -> dict[str, object]:
        """Persist a non-execution so simulations can be audited, not just replayed."""
        now = beijing_now().isoformat()
        with self._connect() as connection:
            account = connection.execute("SELECT available_cash FROM account_cash WHERE account_id='default'").fetchone()
            cash = float(account["available_cash"]) if account else 0.0
            item = {"id": f"skip-{uuid4().hex}", "symbol": symbol, "name": name, "side": "SKIP", "quantity": 0.0, "price": price, "fee": 0.0, "cash_before": cash, "cash_after": cash, "decision_id": decision_id, "reason": reason, "status": "skipped", "executed_at": now}
            connection.execute("INSERT INTO paper_trading_logs (id,symbol,name,side,quantity,price,fee,cash_before,cash_after,decision_id,reason,status,executed_at) VALUES (:id,:symbol,:name,:side,:quantity,:price,:fee,:cash_before,:cash_after,:decision_id,:reason,:status,:executed_at)", item)
        return item

    def active_paper_execution_deferral(self, symbol: str, *, now: datetime | None = None) -> dict[str, object] | None:
        reference = (now or beijing_now()).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_execution_deferrals "
                "WHERE symbol=? AND state='active' AND next_eligible_at>? "
                "ORDER BY created_at DESC LIMIT 1",
                (str(symbol).strip().upper(), reference),
            ).fetchone()
        return dict(row) if row else None

    def defer_paper_execution(
        self, *, decision_id: str, symbol: str, action: str, requested_quantity: float,
        max_executable_quantity: float, reason_code: str, next_eligible_at: str,
        detail: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Persist one T+1 deferral without polluting immutable fill/skip logs."""
        now = beijing_now().isoformat()
        symbol = str(symbol).strip().upper()
        with self._connect() as connection:
            existing_for_decision = connection.execute(
                "SELECT * FROM paper_execution_deferrals WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
            if existing_for_decision:
                return dict(existing_for_decision)
            active = connection.execute(
                "SELECT * FROM paper_execution_deferrals "
                "WHERE symbol=? AND state='active' AND next_eligible_at>? "
                "ORDER BY created_at DESC LIMIT 1",
                (symbol, now),
            ).fetchone()
            if active:
                connection.execute(
                    "UPDATE paper_execution_deferrals SET state='superseded', resolved_at=? "
                    "WHERE decision_id=?",
                    (now, str(active["decision_id"])),
                )
            item = {
                "decision_id": decision_id, "symbol": symbol, "action": action,
                "requested_quantity": float(requested_quantity),
                "max_executable_quantity": float(max_executable_quantity),
                "reason_code": reason_code, "next_eligible_at": next_eligible_at,
                "state": "active", "created_at": now, "resolved_at": None,
                "detail": json.dumps(detail or {}, ensure_ascii=False, default=str),
            }
            connection.execute(
                "INSERT INTO paper_execution_deferrals "
                "(decision_id,symbol,action,requested_quantity,max_executable_quantity,reason_code,"
                "next_eligible_at,state,created_at,resolved_at,detail) VALUES "
                "(:decision_id,:symbol,:action,:requested_quantity,:max_executable_quantity,:reason_code,"
                ":next_eligible_at,:state,:created_at,:resolved_at,:detail) "
                "ON CONFLICT(decision_id) DO NOTHING",
                item,
            )
            row = connection.execute(
                "SELECT * FROM paper_execution_deferrals WHERE decision_id=?", (decision_id,)
            ).fetchone()
        return dict(row) if row else item

    def supersede_due_paper_execution_deferrals(self, symbol: str, *, now: datetime | None = None) -> int:
        """Close elapsed T+1 deferrals before a fresh eligible decision fills."""
        reference = (now or beijing_now()).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE paper_execution_deferrals SET state='superseded', resolved_at=? "
                "WHERE symbol=? AND state='active' AND next_eligible_at<=?",
                (reference, str(symbol).strip().upper(), reference),
            )
        return int(cursor.rowcount)

    def paper_execution_deferrals(self, symbol: str | None = None, state: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        clauses: list[str] = []
        args: list[object] = []
        if symbol:
            clauses.append("symbol=?")
            args.append(str(symbol).strip().upper())
        if state:
            clauses.append("state=?")
            args.append(str(state).strip().lower())
        query = "SELECT * FROM paper_execution_deferrals"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, limit))
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _reconcile_legacy_position_lots(connection, *, symbol: str, market: str, currency: str, now: str) -> bool:
        """Rebuild pre-PositionLot inventory from its immutable paper ledger.

        Earlier installations stored only the aggregate position, but their
        executed paper-trading logs are sufficient to replay FIFO remaining
        inventory.  A mismatch is never guessed: the caller receives an
        explicit reconciliation requirement instead of an invented sellable
        quantity.
        """
        position = connection.execute(
            "SELECT quantity FROM paper_trading_positions WHERE symbol=?", (symbol,)
        ).fetchone()
        if not position or float(position["quantity"]) <= 1e-9:
            return True
        existing_lots = connection.execute(
            "SELECT COUNT(*) AS count FROM paper_position_lots WHERE symbol=?", (symbol,)
        ).fetchone()
        if int(existing_lots["count"]):
            return True
        logs = connection.execute(
            "SELECT id,side,quantity,price,fee,executed_at FROM paper_trading_logs "
            "WHERE symbol=? AND status='executed' AND side IN ('BUY','SELL') "
            "ORDER BY executed_at, id",
            (symbol,),
        ).fetchall()
        replay_lots: list[dict[str, object]] = []
        for log in logs:
            log_quantity = float(log["quantity"])
            if log["side"] == "BUY":
                replay_lots.append({
                    "lot_id": f"legacy-{log['id']}",
                    "quantity": log_quantity,
                    "acquired_at": str(log["executed_at"]),
                    "cost_basis": (log_quantity * float(log["price"]) + float(log["fee"])) / log_quantity,
                })
                continue
            remaining_to_sell = log_quantity
            for lot in replay_lots:
                if remaining_to_sell <= 1e-9:
                    break
                consumed = min(remaining_to_sell, float(lot["quantity"]))
                lot["quantity"] = float(lot["quantity"]) - consumed
                remaining_to_sell -= consumed
            if remaining_to_sell > 1e-9:
                return False
        remaining_quantity = sum(float(lot["quantity"]) for lot in replay_lots)
        if abs(remaining_quantity - float(position["quantity"])) > 1e-6:
            return False
        today = now[:10]
        for lot in replay_lots:
            quantity = float(lot["quantity"])
            if quantity <= 1e-9:
                continue
            is_cn_pending = market == "CN" and str(lot["acquired_at"])[:10] >= today
            connection.execute(
                "INSERT INTO paper_position_lots "
                "(lot_id,symbol,market,currency,quantity,acquired_at,cost_basis,sellable_quantity,settlement_state,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    lot["lot_id"], symbol, market, currency, quantity, lot["acquired_at"], lot["cost_basis"],
                    0.0 if is_cn_pending else quantity,
                    "PENDING_T1" if is_cn_pending else "SETTLED",
                    now,
                ),
            )
        return True

    def execute_paper_trade(self, *, trade_id: str, symbol: str, name: str, side: str, quantity: float, price: float, decision_id: str | None, reason: str, execution_quote_at: str | None = None, execution_quote_source: str | None = None, fill_price_mode: str = "NEXT_ELIGIBLE_OBSERVED_QUOTE") -> dict[str, object]:
        if quantity <= 0 or price <= 0: raise ValueError("quantity_and_price_must_be_positive")
        now_at = beijing_now()
        now = now_at.isoformat()
        with self._connect() as connection:
            from app.market_adapter import adapter_for_market, market_for_symbol

            metadata = connection.execute(
                "SELECT market,lot_size FROM instrument_metadata WHERE symbol=?",
                (str(symbol).strip().upper(),),
            ).fetchone()
            market = str(metadata["market"]).upper() if metadata else market_for_symbol(symbol)
            adapter = adapter_for_market(market)
            if adapter is None:
                raise ValueError("paper_market_rule_unavailable")
            if not self._reconcile_legacy_position_lots(
                connection, symbol=symbol, market=market, currency=adapter.trading_currency, now=now
            ):
                raise ValueError("paper_position_lot_reconciliation_required")
            if adapter.paper_fee_schedule != "CN_A_STANDARD":
                raise ValueError("paper_fee_schedule_unconfigured")
            # For a CN sell, report the substantive availability failure before
            # rejecting a malformed order quantity.  This keeps a retrying
            # scheduler from mistaking an unsellable T+1 position for a lot
            # sizing problem.
            if side == "SELL" and adapter.settlement_rule == "CN_A_T1_SELLABILITY":
                connection.execute(
                    "UPDATE paper_position_lots SET sellable_quantity=quantity, "
                    "settlement_state='SETTLED', updated_at=? "
                    "WHERE symbol=? AND settlement_state='PENDING_T1' AND ("
                    "(sellable_at IS NOT NULL AND sellable_at <= ?) OR "
                    "(sellable_at IS NULL AND substr(acquired_at, 1, 10) < ?))",
                    (now, symbol, now, now_at.date().isoformat()),
                )
                sellable_for_availability = float(connection.execute(
                    "SELECT COALESCE(SUM(sellable_quantity), 0) AS quantity "
                    "FROM paper_position_lots WHERE symbol=? AND quantity > 0",
                    (symbol,),
                ).fetchone()["quantity"])
                if quantity > sellable_for_availability + 1e-9:
                    raise ValueError("paper_t1_unsellable_quantity")
            lot_size = int(metadata["lot_size"]) if metadata and metadata["lot_size"] else adapter.default_lot_size
            if lot_size <= 0:
                raise ValueError("paper_instrument_lot_size_required")
            if quantity % lot_size != 0:
                raise ValueError("paper_quantity_violates_market_lot")
            # The scheduler may wake more than once or restart during an hour.
            # One normalized decision may therefore change this ledger once only.
            if decision_id and connection.execute(
                "SELECT 1 FROM paper_trading_logs WHERE decision_id=? AND side=? LIMIT 1",
                (decision_id, side),
            ).fetchone():
                raise ValueError("paper_decision_already_executed")
            account = connection.execute("SELECT available_cash FROM account_cash WHERE account_id='default'").fetchone()
            cash_before = float(account["available_cash"]) if account else 0.0
            baseline = connection.execute("SELECT initial_cash FROM paper_trading_accounts WHERE account_id='default'").fetchone()
            if baseline is None or float(baseline["initial_cash"]) <= 0:
                connection.execute("INSERT INTO paper_trading_accounts (account_id,available_cash,initial_cash,enabled,updated_at) VALUES ('default', 0, ?, 0, ?) ON CONFLICT(account_id) DO UPDATE SET initial_cash=excluded.initial_cash, updated_at=excluded.updated_at", (cash_before, now))
            position = connection.execute("SELECT * FROM paper_trading_positions WHERE symbol=?", (symbol,)).fetchone()
            existing_quantity = float(position["quantity"]) if position else 0.0
            if side == "BUY":
                gross = quantity * price
                fee = max(5.0, gross * 0.0003)
                cost = gross + fee
                if cost > cash_before + 1e-9: raise ValueError("insufficient_paper_cash_after_fee")
                new_quantity = existing_quantity + quantity
                average_cost = ((float(position["average_cost"]) * existing_quantity) + cost) / new_quantity if position else cost / quantity
                cash_after = cash_before - cost
                connection.execute("INSERT INTO paper_trading_positions VALUES (?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET name=excluded.name,quantity=excluded.quantity,average_cost=excluded.average_cost,updated_at=excluded.updated_at", (symbol, name, new_quantity, average_cost, now))
                connection.execute(
                    "INSERT INTO paper_position_lots "
                    "(lot_id,symbol,market,currency,quantity,acquired_at,cost_basis,sellable_quantity,settlement_state,updated_at,sellable_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid4()), symbol, market, adapter.trading_currency, quantity, now,
                        cost / quantity, 0.0 if adapter.settlement_rule == "CN_A_T1_SELLABILITY" else quantity,
                        "PENDING_T1" if adapter.settlement_rule == "CN_A_T1_SELLABILITY" else "SETTLED", now,
                        self._new_lot_sellable_at(market, now_at),
                    ),
                )
            elif side == "SELL":
                lots = connection.execute(
                    "SELECT lot_id,quantity,sellable_quantity FROM paper_position_lots "
                    "WHERE symbol=? AND quantity > 0 ORDER BY acquired_at, lot_id",
                    (symbol,),
                ).fetchall()
                sellable_quantity = sum(float(lot["sellable_quantity"]) for lot in lots)
                if quantity > sellable_quantity + 1e-9: raise ValueError("paper_t1_unsellable_quantity")
                quantity_remaining_to_sell = quantity
                for lot in lots:
                    if quantity_remaining_to_sell <= 1e-9:
                        break
                    sell_from_lot = min(quantity_remaining_to_sell, float(lot["sellable_quantity"]))
                    quantity_remaining_to_sell -= sell_from_lot
                    remaining_lot_quantity = float(lot["quantity"]) - sell_from_lot
                    connection.execute(
                        "UPDATE paper_position_lots SET quantity=?, sellable_quantity=?, settlement_state=?, updated_at=? WHERE lot_id=?",
                        (
                            remaining_lot_quantity,
                            max(0.0, float(lot["sellable_quantity"]) - sell_from_lot),
                            "CLOSED" if remaining_lot_quantity <= 1e-9 else "SETTLED",
                            now,
                            lot["lot_id"],
                        ),
                    )
                gross = quantity * price
                fee = max(5.0, gross * 0.0003) + gross * 0.001
                cash_after = cash_before + gross - fee
                remaining = existing_quantity - quantity
                if remaining <= 1e-9: connection.execute("DELETE FROM paper_trading_positions WHERE symbol=?", (symbol,))
                else: connection.execute("UPDATE paper_trading_positions SET quantity=?, updated_at=? WHERE symbol=?", (remaining, now, symbol))
            else: raise ValueError("invalid_paper_trade_side")
            connection.execute("INSERT INTO account_cash (account_id,available_cash,updated_at) VALUES ('default', ?, ?) ON CONFLICT(account_id) DO UPDATE SET available_cash=excluded.available_cash, updated_at=excluded.updated_at", (cash_after, now))
            item = {"id": trade_id, "symbol": symbol, "name": name, "side": side, "quantity": quantity, "price": price, "fee": fee, "cash_before": cash_before, "cash_after": cash_after, "decision_id": decision_id, "reason": reason, "execution_quote_at": execution_quote_at, "execution_quote_source": execution_quote_source, "fill_price_mode": fill_price_mode, "executed_at": now}
            connection.execute("INSERT INTO paper_trading_logs (id,symbol,name,side,quantity,price,fee,cash_before,cash_after,decision_id,reason,status,execution_quote_at,execution_quote_source,fill_price_mode,executed_at) VALUES (:id,:symbol,:name,:side,:quantity,:price,:fee,:cash_before,:cash_after,:decision_id,:reason,'executed',:execution_quote_at,:execution_quote_source,:fill_price_mode,:executed_at)", item)
            if decision_id:
                connection.execute(
                    "UPDATE paper_execution_deferrals SET state='released', resolved_at=? "
                    "WHERE decision_id=? AND state='active'",
                    (now, decision_id),
                )
        return item

    def create_simulation_run(self, *, run_id: str, trigger: str, symbols: list[str], message: str) -> dict[str, object]:
        """Open an auditable paper-trading run; every later stage links to run_id."""
        now = beijing_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO simulation_runs (run_id,trigger,started_at,status,symbol_count,message) VALUES (?,?,?,?,?,?)",
                (run_id, trigger, now, "running", len(symbols), message),
            )
        return {"run_id": run_id, "started_at": now, "status": "running", "symbol_count": len(symbols), "message": message}

    def finish_simulation_run(self, *, run_id: str, status: str, message: str, executed: int = 0, skipped: int = 0, generated: int = 0) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE simulation_runs SET finished_at=?, status=?, executed=?, skipped=?, generated=?, message=? WHERE run_id=?",
                (beijing_now().isoformat(), status, int(executed), int(skipped), int(generated), message, run_id),
            )

    def record_simulation_stage(self, *, run_id: str, stage: str, status: str, symbol: str | None = None, detail: dict[str, object] | None = None, started_at: str | None = None) -> None:
        """Append one immutable stage row for a simulation run."""
        started_at = started_at or beijing_now().isoformat()
        finished_at = beijing_now().isoformat()
        elapsed_ms = 0
        try:
            from datetime import datetime
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(finished_at)
            elapsed_ms = max(0, round((end - start).total_seconds() * 1000))
        except (TypeError, ValueError):
            elapsed_ms = 0
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO simulation_run_stages (run_id,stage,symbol,status,detail,started_at,finished_at,elapsed_ms) VALUES (?,?,?,?,?,?,?,?)",
                (run_id, stage, symbol, status, json.dumps(detail or {}, ensure_ascii=False, default=str), started_at, finished_at, elapsed_ms),
            )

    def record_simulation_symbol(self, *, run_id: str, symbol: str, terminal_state: str, detail: dict[str, object] | None = None) -> None:
        """Persist the final per-symbol state so an untraded pass remains auditable."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO simulation_run_symbols (run_id,symbol,terminal_state,detail,updated_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(run_id,symbol) DO UPDATE SET terminal_state=excluded.terminal_state, detail=excluded.detail, updated_at=excluded.updated_at",
                (run_id, symbol.strip().upper(), terminal_state, json.dumps(detail or {}, ensure_ascii=False, default=str), beijing_now().isoformat()),
            )

    def record_daily_history_attempt(self, *, symbol: str, provider: str, status: str, started_at: str, elapsed_ms: int, run_id: str | None = None, trigger: str | None = None, bar_count: int = 0, error_type: str | None = None, error_message: str | None = None, detail: dict[str, object] | None = None) -> None:
        """Persist one observable provider attempt with timing and outcome counts."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO daily_history_provider_attempts (run_id,trigger,symbol,provider,status,started_at,elapsed_ms,bar_count,error_type,error_message,detail) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, trigger, symbol.strip().upper(), provider, status, started_at, max(0, int(elapsed_ms)), max(0, int(bar_count)), error_type, error_message, json.dumps(detail or {}, ensure_ascii=False, default=str)),
            )

    def latest_daily_history_failure(self, symbol: str) -> dict[str, object] | None:
        """Most recent symbol-level history failure, used to enforce a restart-safe backoff."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT started_at, elapsed_ms, error_type, error_message FROM daily_history_provider_attempts "
                "WHERE symbol=? AND provider='overall' AND status='error' ORDER BY started_at DESC LIMIT 1",
                (symbol.strip().upper(),),
            ).fetchone()
        return dict(row) if row else None

    def daily_history_attempts(self, symbol: str | None = None, limit: int = 200) -> list[dict[str, object]]:
        query, args = "SELECT * FROM daily_history_provider_attempts", []
        if symbol:
            query += " WHERE symbol=?"
            args.append(symbol.strip().upper())
        query += " ORDER BY started_at DESC LIMIT ?"
        args.append(max(1, min(limit, 1000)))
        with self._connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [{**dict(row), "detail": json.loads(str(row["detail"]))} for row in rows]

    def record_provider_health(self, *, provider: str, success: bool, error_type: str | None = None, error_message: str | None = None, circuit_threshold: int = 3, cooldown_seconds: int = 600) -> dict[str, object]:
        """Update one provider's counters and open/close its circuit breaker."""
        now = beijing_now()
        now_text = now.isoformat()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM data_provider_health WHERE provider=?", (provider,)).fetchone()
            previous = dict(row) if row else {}
            consecutive = int(previous.get("consecutive_failures", 0))
            total_attempts = int(previous.get("total_attempts", 0)) + 1
            total_success = int(previous.get("total_success", 0)) + (1 if success else 0)
            total_failures = int(previous.get("total_failures", 0)) + (0 if success else 1)
            consecutive = 0 if success else consecutive + 1
            circuit_state = "closed"
            circuit_opened_at: str | None = None
            cooldown_until: str | None = None
            if not success and consecutive >= max(1, circuit_threshold):
                circuit_state = "open"
                circuit_opened_at = now_text
                cooldown_until = (now + timedelta(seconds=max(1, cooldown_seconds))).isoformat()
            connection.execute(
                "INSERT INTO data_provider_health (provider,circuit_state,consecutive_failures,total_attempts,total_success,total_failures,last_attempt_at,last_success_at,last_failure_at,circuit_opened_at,cooldown_until,error_type,error_message,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(provider) DO UPDATE SET circuit_state=excluded.circuit_state, consecutive_failures=excluded.consecutive_failures, total_attempts=excluded.total_attempts, total_success=excluded.total_success, total_failures=excluded.total_failures, last_attempt_at=excluded.last_attempt_at, last_success_at=excluded.last_success_at, last_failure_at=excluded.last_failure_at, circuit_opened_at=excluded.circuit_opened_at, cooldown_until=excluded.cooldown_until, error_type=excluded.error_type, error_message=excluded.error_message, updated_at=excluded.updated_at",
                (provider, circuit_state, consecutive, total_attempts, total_success, total_failures,
                 now_text, now_text if success else previous.get("last_success_at"), now_text if not success else previous.get("last_failure_at"),
                 circuit_opened_at, cooldown_until, error_type, error_message, now_text),
            )
        return self.provider_health(provider) or {"provider": provider, "circuit_state": "closed"}

    def provider_health(self, provider: str) -> dict[str, object] | None:
        """Return one provider's health; an expired cooldown automatically closes the circuit."""
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM data_provider_health WHERE provider=?", (provider,)).fetchone()
            if not row:
                return None
            item = dict(row)
            if item.get("circuit_state") == "open" and item.get("cooldown_until"):
                try:
                    from datetime import datetime
                    cooldown_end = datetime.fromisoformat(str(item["cooldown_until"]))
                    if beijing_now() >= cooldown_end:
                        item["circuit_state"] = "closed"
                        item["consecutive_failures"] = 0
                        item["circuit_opened_at"] = None
                        item["cooldown_until"] = None
                        connection.execute(
                            "UPDATE data_provider_health SET circuit_state='closed', consecutive_failures=0, circuit_opened_at=NULL, cooldown_until=NULL, updated_at=? WHERE provider=?",
                            (beijing_now().isoformat(), provider),
                        )
                except (TypeError, ValueError):
                    pass
        return item

    def provider_health_summary(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM data_provider_health ORDER BY provider ASC").fetchall()
        return [dict(row) for row in rows]

    def provider_circuit_open(self, provider: str) -> bool:
        health = self.provider_health(provider)
        return bool(health and health.get("circuit_state") == "open")

    def failed_history_symbols(self, since_hours: int = 24, limit: int = 100) -> list[dict[str, object]]:
        """Symbols whose daily-history preparation failed recently, newest first.

        The queue combines provider-level overall failures with simulation
        terminal states so a stock blocked only by missing bars is retried too.
        A symbol whose most recent overall refresh succeeded drops out even if
        an older failure row remains in the append-only attempt log.
        """
        candidates: dict[str, str] = {}
        latest_overall: dict[str, str] = {}
        now = beijing_now()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT a.symbol, a.started_at, a.status
                   FROM daily_history_provider_attempts a
                   WHERE a.provider='overall'
                     AND a.started_at = (SELECT MAX(b.started_at) FROM daily_history_provider_attempts b WHERE b.provider='overall' AND b.symbol=a.symbol)"""
            ).fetchall()
            for row in rows:
                symbol = str(row["symbol"])
                latest_overall[symbol] = str(row["status"])
                if str(row["status"]) == "error" and symbol not in candidates:
                    candidates[symbol] = str(row["started_at"])
            symbol_rows = connection.execute(
                "SELECT symbol, updated_at FROM simulation_run_symbols WHERE terminal_state='skipped_data_unavailable' ORDER BY updated_at DESC"
            ).fetchall()
            for row in symbol_rows:
                symbol = str(row["symbol"])
                # Simulation terminal states fill gaps where no refresh was
                # attempted; an existing successful refresh takes precedence.
                if symbol not in candidates and latest_overall.get(symbol) != "ok":
                    candidates[symbol] = str(row["updated_at"])
        filtered: list[tuple[str, str]] = []
        for symbol, moment in candidates.items():
            try:
                parsed = datetime.fromisoformat(moment)
            except ValueError:
                parsed = None
            if parsed is not None and parsed.tzinfo is None:
                # Naive timestamps produced by tests or older rows are Beijing time.
                parsed = parsed.replace(tzinfo=timezone(timedelta(hours=8)))
            if parsed is None or (now - parsed).total_seconds() <= max(1, since_hours) * 3600:
                filtered.append((symbol, moment))
        filtered.sort(key=lambda item: item[1], reverse=True)
        return [{"symbol": symbol, "failed_at": moment} for symbol, moment in filtered[:max(1, min(limit, 500))]]

    def simulation_runs(self, limit: int = 50) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, trigger, started_at, finished_at, status, symbol_count, generated, executed, skipped, message "
                "FROM simulation_runs ORDER BY started_at DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def simulation_run(self, run_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_id, trigger, started_at, finished_at, status, symbol_count, generated, executed, skipped, message "
                "FROM simulation_runs WHERE run_id=?", (run_id,),
            ).fetchone()
            if not row:
                return None
            stages = [dict(item) for item in connection.execute(
                "SELECT id, stage, symbol, status, detail, started_at, finished_at, elapsed_ms "
                "FROM simulation_run_stages WHERE run_id=? ORDER BY id ASC", (run_id,),
            ).fetchall()]
            symbols = [dict(item) for item in connection.execute(
                "SELECT symbol, terminal_state, detail, updated_at FROM simulation_run_symbols WHERE run_id=? ORDER BY symbol ASC", (run_id,),
            ).fetchall()]
        for stage in stages:
            stage["detail"] = json.loads(str(stage["detail"]))
        for item in symbols:
            item["detail"] = json.loads(str(item["detail"]))
        return {**dict(row), "stages": stages, "symbols": symbols}

    def enqueue_ai_job(self, job: dict[str, object]) -> dict[str, object]:
        now = beijing_now().isoformat()
        with self._connect() as connection:
            existing = connection.execute("SELECT * FROM ai_jobs WHERE input_hash=?", (job["input_hash"],)).fetchone()
            if existing: return dict(existing) | {"payload": json.loads(str(existing["payload"]))}
            connection.execute("INSERT INTO ai_jobs VALUES (?, ?, ?, 'pending', 0, ?, ?, NULL, ?, ?)", (job["id"], job["target_id"], job["input_hash"], job.get("max_attempts", 3), json.dumps(job["payload"], ensure_ascii=False, default=str), now, now))
        return {**job, "status": "pending", "attempts": 0, "created_at": now, "updated_at": now}

    def ai_jobs(self, target_id: str | None = None) -> list[dict[str, object]]:
        query, params = ("SELECT * FROM ai_jobs WHERE target_id=? ORDER BY updated_at DESC", [target_id]) if target_id else ("SELECT * FROM ai_jobs ORDER BY updated_at DESC", [])
        with self._connect() as connection: rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "payload": json.loads(str(row["payload"]))} for row in rows]

    def update_ai_job(self, job_id: str, status: str, error_message: str | None = None, increment_attempt: bool = False) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE ai_jobs SET status=?, attempts=attempts+?, error_message=?, updated_at=? WHERE id=?", (status, 1 if increment_attempt else 0, error_message, beijing_now().isoformat(), job_id))
