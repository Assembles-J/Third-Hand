"""Small SQLite persistence layer for the MVP portfolio."""
from __future__ import annotations

import os
import sqlite3
import json
import math
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
                connection.execute("CREATE TABLE IF NOT EXISTS research_recommendations (id TEXT PRIMARY KEY, symbol TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS daily_reviews (id TEXT PRIMARY KEY, review_date TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS recommendation_evaluations (recommendation_id TEXT NOT NULL, horizon INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(recommendation_id, horizon))")
                connection.execute("CREATE TABLE IF NOT EXISTS recommendation_events (id INTEGER PRIMARY KEY AUTOINCREMENT, recommendation_id TEXT NOT NULL, event_type TEXT NOT NULL, trading_date TEXT, trigger_price REAL, payload TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_positions (recommendation_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, action TEXT NOT NULL, quantity REAL NOT NULL, fill_price REAL NOT NULL, fill_date TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_daily_pnl (recommendation_id TEXT NOT NULL, trading_date TEXT NOT NULL, close_price REAL NOT NULL, gross_pnl REAL NOT NULL, net_pnl REAL NOT NULL, quantity REAL NOT NULL, PRIMARY KEY(recommendation_id, trading_date))")
                connection.execute("CREATE TABLE IF NOT EXISTS ai_jobs (id TEXT PRIMARY KEY, target_id TEXT NOT NULL, input_hash TEXT NOT NULL UNIQUE, status TEXT NOT NULL, attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL, payload TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS account_cash (account_id TEXT PRIMARY KEY, available_cash REAL NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_accounts (account_id TEXT PRIMARY KEY, available_cash REAL NOT NULL, initial_cash REAL NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_positions (symbol TEXT PRIMARY KEY, name TEXT NOT NULL, quantity REAL NOT NULL, average_cost REAL NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_logs (id TEXT PRIMARY KEY, symbol TEXT NOT NULL, name TEXT NOT NULL, side TEXT NOT NULL, quantity REAL NOT NULL, price REAL NOT NULL, fee REAL NOT NULL DEFAULT 0, cash_before REAL NOT NULL, cash_after REAL NOT NULL, decision_id TEXT, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'executed', executed_at TEXT NOT NULL)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_paper_trading_logs_symbol_time ON paper_trading_logs(symbol, executed_at DESC)")
                connection.execute("CREATE TABLE IF NOT EXISTS paper_trading_equity_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, total_equity REAL NOT NULL, available_cash REAL NOT NULL, market_value REAL NOT NULL, total_pnl REAL NOT NULL, recorded_at TEXT NOT NULL)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_paper_equity_snapshots_time ON paper_trading_equity_snapshots(recorded_at DESC)")
                self._ensure_column(connection, "paper_trading_logs", "status", "TEXT NOT NULL DEFAULT 'executed'")
                self._ensure_column(connection, "paper_trading_logs", "fee", "REAL NOT NULL DEFAULT 0")
                self._ensure_column(connection, "paper_trading_accounts", "initial_cash", "REAL NOT NULL DEFAULT 0")
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS calibration_observations (
                        id TEXT PRIMARY KEY,
                        analysis_run_id TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        action TEXT NOT NULL,
                        entry_date TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(symbol, action, entry_date)
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_calibration_observations_symbol_date ON calibration_observations(symbol, entry_date DESC)")
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
            connection.execute("DELETE FROM research_recommendations")
            connection.execute("DELETE FROM recommendation_evaluations")
            connection.execute("DELETE FROM recommendation_events")
            connection.execute("DELETE FROM paper_positions")
            connection.execute("DELETE FROM paper_daily_pnl")
            connection.execute("DELETE FROM ai_jobs")
            connection.execute("DELETE FROM account_cash")
            connection.execute("DELETE FROM calibration_observations")
            connection.execute("DELETE FROM ai_analysis_cache")
            connection.execute("DELETE FROM ai_analysis_cache_v2")
            connection.execute("DELETE FROM content_cache")
            connection.execute("DELETE FROM glossary_entries")
            connection.execute("DELETE FROM glossary_lookup_history")
            connection.execute("DELETE FROM decision_contexts")
            connection.execute("DELETE FROM decision_shadow_reports")
            connection.execute("DELETE FROM decision_ai_runs")
            connection.execute("DELETE FROM decision_reports")
            connection.execute("DELETE FROM decision_jobs")

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

    def cached_content(self, symbols: list[str] | None = None, limit: int = 80) -> list[dict[str, object]]:
        """Return source-linked content retained locally for evidence assembly."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM content_cache ORDER BY updated_at DESC LIMIT ?", (max(1, limit),)
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

    def save_calibration_observations(self, analysis_run: dict[str, object]) -> None:
        """Keep one source snapshot per symbol/action/trading date for later calibration."""
        rows = []
        for item in analysis_run.get("items", []):
            snapshot = item.get("decision_snapshot") or {}
            quote = snapshot.get("quote") or {}
            price = quote.get("price")
            entry_date = str(quote.get("as_of") or analysis_run.get("generated_at", ""))[:10]
            if price is None or not entry_date:
                continue
            rows.append((
                f"{item['symbol']}:{item['action']}:{entry_date}", str(analysis_run["id"]), str(item["symbol"]),
                str(item["action"]), entry_date, float(price), json.dumps(snapshot, ensure_ascii=False, default=str),
                beijing_now().isoformat(),
            ))
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO calibration_observations "
                "(id, analysis_run_id, symbol, action, entry_date, entry_price, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def calibration_observations(self, symbol: str | None = None) -> list[dict[str, object]]:
        query, params = (
            ("SELECT symbol, action, entry_date, entry_price, payload FROM calibration_observations WHERE symbol=? ORDER BY entry_date", [symbol])
            if symbol else ("SELECT symbol, action, entry_date, entry_price, payload FROM calibration_observations ORDER BY entry_date", [])
        )
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "payload": json.loads(str(row["payload"]))} for row in rows]

    def save_recommendation(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO research_recommendations VALUES (?, ?, ?, ?)", (item["id"], item["symbol"], json.dumps(item, ensure_ascii=False), beijing_now().isoformat()))

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
            connection.execute("INSERT INTO account_cash VALUES ('default', ?, ?) ON CONFLICT(account_id) DO UPDATE SET available_cash=excluded.available_cash, updated_at=excluded.updated_at", (available_cash, now))
        return {"available_cash": available_cash, "updated_at": now}

    def paper_account(self) -> dict[str, object]:
        settings = self.system_settings()
        with self._connect() as connection:
            cash_row = connection.execute("SELECT available_cash, updated_at FROM account_cash WHERE account_id='default'").fetchone()
            row = connection.execute("SELECT initial_cash FROM paper_trading_accounts WHERE account_id='default'").fetchone()
            positions = [dict(item) for item in connection.execute("SELECT * FROM paper_trading_positions ORDER BY updated_at DESC").fetchall()]
            quotes = {str(item["symbol"]): json.loads(str(item["payload"])) for item in connection.execute("SELECT symbol,payload FROM market_quote_cache").fetchall()}
        enriched_positions = []
        for position in positions:
            price = float((quotes.get(str(position["symbol"]), {}).get("price")) or position["average_cost"])
            market_value = float(position["quantity"]) * price
            cost_value = float(position["quantity"]) * float(position["average_cost"])
            enriched_positions.append({**position, "last_price": price, "market_value": market_value, "unrealized_pnl": market_value - cost_value, "unrealized_return_percent": (market_value / cost_value - 1) * 100 if cost_value else 0.0})
        positions = enriched_positions
        market_value = sum(float(position["market_value"]) for position in positions)
        cash = float(cash_row["available_cash"]) if cash_row else 0.0
        initial_cash = float(row["initial_cash"]) if row else 0.0
        equity = cash + market_value
        return {"available_cash": cash, "initial_cash": initial_cash, "market_value": market_value, "total_equity": equity, "total_pnl": equity - initial_cash, "total_return_percent": (equity / initial_cash - 1) * 100 if initial_cash else 0.0, "updated_at": cash_row["updated_at"] if cash_row else beijing_now().isoformat(), "enabled": settings["paper_trading_enabled"], "positions": positions}

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

    def record_paper_skip(self, *, symbol: str, name: str, decision_id: str | None, reason: str, price: float = 0.0) -> dict[str, object]:
        """Persist a non-execution so simulations can be audited, not just replayed."""
        now = beijing_now().isoformat()
        with self._connect() as connection:
            account = connection.execute("SELECT available_cash FROM account_cash WHERE account_id='default'").fetchone()
            cash = float(account["available_cash"]) if account else 0.0
            item = {"id": f"skip-{uuid4().hex}", "symbol": symbol, "name": name, "side": "SKIP", "quantity": 0.0, "price": price, "fee": 0.0, "cash_before": cash, "cash_after": cash, "decision_id": decision_id, "reason": reason, "status": "skipped", "executed_at": now}
            connection.execute("INSERT INTO paper_trading_logs (id,symbol,name,side,quantity,price,fee,cash_before,cash_after,decision_id,reason,status,executed_at) VALUES (:id,:symbol,:name,:side,:quantity,:price,:fee,:cash_before,:cash_after,:decision_id,:reason,:status,:executed_at)", item)
        return item

    def execute_paper_trade(self, *, trade_id: str, symbol: str, name: str, side: str, quantity: float, price: float, decision_id: str | None, reason: str) -> dict[str, object]:
        if quantity <= 0 or price <= 0: raise ValueError("quantity_and_price_must_be_positive")
        if side == "BUY" and quantity % 100 != 0: raise ValueError("paper_buy_requires_100_share_lot")
        now = beijing_now().isoformat()
        with self._connect() as connection:
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
            elif side == "SELL":
                if quantity > existing_quantity + 1e-9: raise ValueError("insufficient_paper_position")
                gross = quantity * price
                fee = max(5.0, gross * 0.0003) + gross * 0.001
                cash_after = cash_before + gross - fee
                remaining = existing_quantity - quantity
                if remaining <= 1e-9: connection.execute("DELETE FROM paper_trading_positions WHERE symbol=?", (symbol,))
                else: connection.execute("UPDATE paper_trading_positions SET quantity=?, updated_at=? WHERE symbol=?", (remaining, now, symbol))
            else: raise ValueError("invalid_paper_trade_side")
            connection.execute("INSERT INTO account_cash (account_id,available_cash,updated_at) VALUES ('default', ?, ?) ON CONFLICT(account_id) DO UPDATE SET available_cash=excluded.available_cash, updated_at=excluded.updated_at", (cash_after, now))
            item = {"id": trade_id, "symbol": symbol, "name": name, "side": side, "quantity": quantity, "price": price, "fee": fee, "cash_before": cash_before, "cash_after": cash_after, "decision_id": decision_id, "reason": reason, "executed_at": now}
            connection.execute("INSERT INTO paper_trading_logs (id,symbol,name,side,quantity,price,fee,cash_before,cash_after,decision_id,reason,status,executed_at) VALUES (:id,:symbol,:name,:side,:quantity,:price,:fee,:cash_before,:cash_after,:decision_id,:reason,'executed',:executed_at)", item)
        return item

    def recommendations(self, symbol: str | None = None) -> list[dict[str, object]]:
        query, args = ("SELECT payload FROM research_recommendations WHERE symbol=? ORDER BY created_at DESC", [symbol]) if symbol else ("SELECT payload FROM research_recommendations ORDER BY created_at DESC", [])
        with self._connect() as connection: rows = connection.execute(query, args).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def set_recommendation_evaluation_status(self, recommendation_id: str, evaluation_status: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM research_recommendations WHERE id=?", (recommendation_id,)).fetchone()
            if not row:
                return False
            payload = json.loads(str(row["payload"]))
            if payload.get("evaluation_status") == evaluation_status:
                return False
            payload["evaluation_status"] = evaluation_status
            connection.execute("UPDATE research_recommendations SET payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), recommendation_id))
        return True

    def save_evaluations(self, recommendation_id: str, items: list[dict[str, object]]) -> None:
        with self._connect() as connection:
            connection.executemany("INSERT OR REPLACE INTO recommendation_evaluations VALUES (?, ?, ?)", [(recommendation_id, int(item["horizon"]), json.dumps(item, ensure_ascii=False)) for item in items])

    def recommendation_evaluations(self, recommendation_id: str) -> list[dict[str, object]]:
        with self._connect() as connection: rows = connection.execute("SELECT payload FROM recommendation_evaluations WHERE recommendation_id=? ORDER BY horizon", (recommendation_id,)).fetchall()
        return [json.loads(str(row["payload"])) for row in rows]

    def save_recommendation_events(self, recommendation_id: str, events: list[dict[str, object]]) -> None:
        if not events:
            return
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO recommendation_events (recommendation_id,event_type,trading_date,trigger_price,payload) VALUES (?, ?, ?, ?, ?)",
                [(recommendation_id, str(event.get("event_type", "condition_checked")), event.get("trading_date"), event.get("trigger_price"), json.dumps(event, ensure_ascii=False, default=str)) for event in events],
            )

    def save_paper_tracking(self, recommendation_id: str, symbol: str, fill: dict[str, object], quantity: float, action: str, bars: list[dict[str, object]]) -> None:
        entry = float(fill["price"])
        sign = -1 if action == "trim" else 1
        now = beijing_now().isoformat()
        rows = []
        for bar in bars:
            close = float(bar["close"])
            gross = (close - entry) * quantity * sign
            fees = (entry + close) * quantity * 0.0003
            rows.append((recommendation_id, str(bar["trading_date"]), close, gross, gross - fees, quantity))
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO paper_positions VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
                (recommendation_id, symbol, action, quantity, entry, str(fill["date"]), now),
            )
            connection.executemany("INSERT OR REPLACE INTO paper_daily_pnl VALUES (?, ?, ?, ?, ?, ?)", rows)

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
