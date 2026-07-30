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
                        created_at TEXT NOT NULL,
                        lookup_status TEXT NOT NULL DEFAULT 'pending',
                        lookup_message TEXT NOT NULL DEFAULT '',
                        lookup_updated_at TEXT
                    )
                """)
                self._ensure_column(connection, "holding_drafts", "lookup_status", "TEXT NOT NULL DEFAULT 'pending'")
                self._ensure_column(connection, "holding_drafts", "lookup_message", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "holding_drafts", "lookup_updated_at", "TEXT")
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
                connection.execute("CREATE TABLE IF NOT EXISTS risk_cache (symbol TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS portfolio_analysis_cache (analysis_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS learning_cases (id TEXT PRIMARY KEY, symbol TEXT, title TEXT NOT NULL, context TEXT NOT NULL, lesson TEXT NOT NULL, outcome TEXT NOT NULL, position_band TEXT NOT NULL DEFAULT '', planned_action TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0.5, evidence_links TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS research_rules (id TEXT PRIMARY KEY, category TEXT NOT NULL, title TEXT NOT NULL, trigger_text TEXT NOT NULL, guidance TEXT NOT NULL, confidence_ceiling REAL NOT NULL, source_url TEXT NOT NULL, version TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS personal_rules (id TEXT PRIMARY KEY, scope TEXT NOT NULL, symbol TEXT, max_position_percent REAL NOT NULL, loss_review_percent REAL NOT NULL, volatility_review_percent REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS analysis_runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
                self._ensure_column(connection, "learning_cases", "position_band", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "learning_cases", "planned_action", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(connection, "learning_cases", "confidence", "REAL NOT NULL DEFAULT 0.5")
                self._ensure_column(connection, "learning_cases", "evidence_links", "TEXT NOT NULL DEFAULT '[]'")
                self._seed_research_rules(connection)

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
            "lookup_status": "pending", "lookup_message": "等待后台查询证券代码", "lookup_updated_at": None,
        }
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO holding_drafts
                (id, name, quantity, average_cost, created_at, lookup_status, lookup_message, lookup_updated_at)
                VALUES (:id, :name, :quantity, :average_cost, :created_at, :lookup_status, :lookup_message, :lookup_updated_at)""",
                item,
            )
        return item

    def add_drafts(self, drafts: list[dict[str, object]]) -> list[dict[str, object]]:
        for draft in drafts:
            draft.setdefault("lookup_status", "pending")
            draft.setdefault("lookup_message", "等待后台查询证券代码")
            draft.setdefault("lookup_updated_at", None)
        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO holding_drafts
                (id, name, quantity, average_cost, created_at, lookup_status, lookup_message, lookup_updated_at)
                VALUES (:id, :name, :quantity, :average_cost, :created_at, :lookup_status, :lookup_message, :lookup_updated_at)""",
                drafts,
            )
        return drafts

    def drafts_by_ids(self, draft_ids: list[str]) -> list[dict[str, object]]:
        if not draft_ids:
            return []
        placeholders = ",".join("?" for _ in draft_ids)
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM holding_drafts WHERE id IN ({placeholders})", draft_ids).fetchall()
        return [dict(row) for row in rows]

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

    def update(self, holding_id: str, symbol: str, name: str, quantity: float, average_cost: float) -> dict[str, object] | None:
        with self._connect() as connection:
            current = connection.execute("SELECT id FROM holdings WHERE id = ?", (holding_id,)).fetchone()
            if not current: return None
            duplicate = connection.execute("SELECT id FROM holdings WHERE symbol = ? AND id != ?", (symbol, holding_id)).fetchone()
            if duplicate:
                connection.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
                holding_id = str(duplicate["id"])
            item = {"id": holding_id, "symbol": symbol, "name": name, "quantity": quantity, "average_cost": average_cost, "created_at": beijing_now().isoformat()}
            connection.execute("UPDATE holdings SET symbol=:symbol,name=:name,quantity=:quantity,average_cost=:average_cost,created_at=:created_at WHERE id=:id", item)
        return item

    def delete_draft(self, draft_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM holding_drafts WHERE id = ?", (draft_id,))
        return result.rowcount > 0

    def clear_for_test(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM holdings")
            connection.execute("DELETE FROM holding_drafts")
            connection.execute("DELETE FROM market_quote_cache")
            connection.execute("DELETE FROM symbol_lookup_cache")
            connection.execute("DELETE FROM personal_rules")
            connection.execute("DELETE FROM learning_cases")
            connection.execute("DELETE FROM risk_cache")
            connection.execute("DELETE FROM portfolio_analysis_cache")
            connection.execute("DELETE FROM analysis_runs")
            connection.execute("DELETE FROM ai_analysis_cache")
            connection.execute("DELETE FROM ai_analysis_cache_v2")
            connection.execute("DELETE FROM content_cache")

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
                "cached_content_count": connection.execute("SELECT COUNT(*) FROM content_cache").fetchone()[0],
            }
        counts["database_bytes"] = self.database_path.stat().st_size if self.database_path.exists() else 0
        return {key: int(value) for key, value in counts.items()}

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

    def save_risk(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO risk_cache (symbol, payload, updated_at) VALUES (?, ?, ?) ON CONFLICT(symbol) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (str(item["symbol"]), json.dumps(item, ensure_ascii=False, default=str), beijing_now().isoformat()))

    def save_portfolio_analysis(self, payload: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO portfolio_analysis_cache (analysis_key, payload, updated_at) VALUES ('current', ?, ?) ON CONFLICT(analysis_key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", (json.dumps(payload, ensure_ascii=False, default=str), beijing_now().isoformat()))

    def cached_risk(self, symbol: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM risk_cache WHERE symbol = ?", (symbol,)).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def add_learning_case(self, item: dict[str, object]) -> dict[str, object]:
        with self._connect() as connection:
            item["evidence_links"] = json.dumps(item.get("evidence_links", []), ensure_ascii=False)
            connection.execute("INSERT INTO learning_cases (id, symbol, title, context, lesson, outcome, position_band, planned_action, confidence, evidence_links, created_at) VALUES (:id,:symbol,:title,:context,:lesson,:outcome,:position_band,:planned_action,:confidence,:evidence_links,:created_at)", item)
        return {**item, "evidence_links": json.loads(str(item["evidence_links"]))}

    def learning_cases(self, symbol: str | None = None) -> list[dict[str, object]]:
        query, params = ("SELECT * FROM learning_cases WHERE symbol=? OR symbol IS NULL ORDER BY created_at DESC", [symbol]) if symbol else ("SELECT * FROM learning_cases ORDER BY created_at DESC", [])
        with self._connect() as connection: rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "evidence_links": json.loads(str(row["evidence_links"]))} for row in rows]

    def research_rules(self) -> list[dict[str, object]]:
        with self._connect() as connection: rows = connection.execute("SELECT * FROM research_rules ORDER BY category, id").fetchall()
        return [dict(row) for row in rows]

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

    def save_analysis_run(self, item: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO analysis_runs (id, payload, created_at) VALUES (?, ?, ?)", (str(item["id"]), json.dumps(item, ensure_ascii=False, default=str), beijing_now().isoformat()))
