"""SQLite-backed security directory cache for market symbol search.

The directory is a rebuildable v2 projection over identities Third-Hand has
already persisted. It never performs provider I/O and follows the same
repository-owned schema pattern as CandidateRepository.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from threading import Lock

from app.time_utils import beijing_now


ETF_PREFIXES = ("15", "16", "51", "56", "58")


def normalize_search_text(value: object) -> str:
    return re.sub(r"[\s\-_.·・()（）%]", "", str(value or "")).upper()


def market_for_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if len(value) == 5 and value.isdigit():
        return "HK"
    if len(value) == 6 and value.isdigit() and value.startswith(ETF_PREFIXES):
        return "ETF"
    return "CN"


def currency_for_market(market: str) -> str:
    return "HKD" if market == "HK" else "CNY"


class SymbolSearchRepository:
    """Persist and query security identity data without touching live providers."""

    RESYNC_SECONDS = 30

    def __init__(self, store) -> None:
        self.store = store
        self._seed_lock = Lock()
        self._last_seed_monotonic = 0.0
        self.ensure_schema()
        self.seed_from_existing_data()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS security_directory_cache (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(market, symbol)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_security_directory_symbol "
                "ON security_directory_cache(symbol)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_security_directory_name "
                "ON security_directory_cache(normalized_name)"
            )

    def seed_from_existing_data(self) -> None:
        """Warm the directory from identities already persisted by Third-Hand."""
        with self._seed_lock:
            candidates: list[dict[str, str]] = []
            legacy_candidates: list[dict[str, str]] = []

            for quote in self.store.all_cached_quotes(limit=5000):
                symbol = str(quote.get("symbol") or "").strip().upper()
                name = str(quote.get("name") or symbol).strip()
                if not symbol:
                    continue
                market = market_for_symbol(symbol)
                candidates.append(
                    {
                        "symbol": symbol,
                        "name": name or symbol,
                        "market": market,
                        "currency": str(quote.get("currency") or currency_for_market(market)),
                        "match_type": "database",
                    }
                )

            with self.store._connect() as connection:
                for table in ("holdings", "watchlist", "paper_trading_positions", "candidate_entries"):
                    try:
                        rows = connection.execute(f"SELECT symbol,name FROM {table}").fetchall()
                    except Exception:
                        continue
                    for row in rows:
                        symbol = str(row["symbol"] or "").strip().upper()
                        name = str(row["name"] or symbol).strip()
                        if not symbol:
                            continue
                        market = market_for_symbol(symbol)
                        candidates.append(
                            {
                                "symbol": symbol,
                                "name": name or symbol,
                                "market": market,
                                "currency": currency_for_market(market),
                                "match_type": "database",
                            }
                        )

                lookup_rows = connection.execute(
                    "SELECT payload FROM symbol_lookup_cache"
                ).fetchall()

            for row in lookup_rows:
                try:
                    payload = json.loads(str(row["payload"] or "[]"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, list):
                    continue
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    symbol = str(item.get("symbol") or "").strip().upper()
                    if not symbol:
                        continue
                    market = str(item.get("market") or market_for_symbol(symbol)).strip().upper()
                    name = str(item.get("name") or symbol).strip() or symbol
                    legacy_candidates.append(
                        {
                            "symbol": symbol,
                            "name": name,
                            "market": market,
                            "currency": str(item.get("currency") or currency_for_market(market)).strip().upper(),
                            "match_type": "database",
                        }
                    )

            self.upsert_candidates(candidates, source="existing_database")
            self.upsert_candidates(legacy_candidates, source="symbol_lookup_cache")
            self._last_seed_monotonic = time.monotonic()

    def _resync_if_due(self) -> None:
        if time.monotonic() - self._last_seed_monotonic >= self.RESYNC_SECONDS:
            self.seed_from_existing_data()

    def upsert_candidates(self, candidates: list[dict[str, object]], *, source: str) -> None:
        if not candidates:
            return
        now = beijing_now().isoformat()
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        for item in candidates:
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            market = str(item.get("market") or market_for_symbol(symbol)).strip().upper()
            name = str(item.get("name") or symbol).strip() or symbol
            currency = str(item.get("currency") or currency_for_market(market)).strip().upper()
            rows.append((market, symbol, name, normalize_search_text(name), currency, source, now))
        if not rows:
            return
        with self.store._connect() as connection:
            connection.executemany(
                """
                INSERT INTO security_directory_cache(
                    market,symbol,name,normalized_name,currency,source,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(market,symbol) DO UPDATE SET
                    name=excluded.name,
                    normalized_name=excluded.normalized_name,
                    currency=excluded.currency,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                rows,
            )

    def local_search(self, query: str, *, limit: int = 20) -> list[dict[str, str]]:
        self._resync_if_due()
        cleaned = str(query or "").strip().upper()
        normalized = normalize_search_text(cleaned)
        if not normalized:
            return []
        padded_hk = cleaned.zfill(5) if cleaned.isdigit() and len(cleaned) < 5 else cleaned
        with self.store._connect() as connection:
            rows = connection.execute(
                """
                SELECT market,symbol,name,currency,
                    CASE
                        WHEN symbol=? OR symbol=? THEN 100
                        WHEN normalized_name=? THEN 95
                        WHEN symbol LIKE ? THEN 90
                        WHEN normalized_name LIKE ? THEN 80
                        WHEN normalized_name LIKE ? THEN 70
                        ELSE 0
                    END AS score
                FROM security_directory_cache
                WHERE symbol=? OR symbol=?
                   OR symbol LIKE ?
                   OR normalized_name=?
                   OR normalized_name LIKE ?
                ORDER BY score DESC, symbol ASC
                LIMIT ?
                """,
                (
                    cleaned,
                    padded_hk,
                    normalized,
                    f"{cleaned}%",
                    f"{normalized}%",
                    f"%{normalized}%",
                    cleaned,
                    padded_hk,
                    f"{cleaned}%",
                    normalized,
                    f"%{normalized}%",
                    max(1, min(int(limit), 50)),
                ),
            ).fetchall()
        return [
            {
                "symbol": str(row["symbol"]),
                "name": str(row["name"]),
                "market": str(row["market"]),
                "currency": str(row["currency"]),
                "match_type": "database",
            }
            for row in rows
        ]

    def cached_lookup(self, query: str) -> dict[str, object] | None:
        key = str(query or "").strip()
        if not key:
            return None
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT payload,updated_at FROM symbol_lookup_cache WHERE name=?",
                (key,),
            ).fetchone()
        if not row:
            return None
        try:
            matches = json.loads(str(row["payload"] or "[]"))
        except json.JSONDecodeError:
            matches = []
        updated_at = str(row["updated_at"] or "")
        age_seconds: int | None = None
        try:
            updated = datetime.fromisoformat(updated_at)
            now = beijing_now()
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=now.tzinfo)
            age_seconds = max(0, int((now - updated.astimezone(now.tzinfo)).total_seconds()))
        except (TypeError, ValueError):
            pass
        return {
            "matches": matches if isinstance(matches, list) else [],
            "updated_at": updated_at,
            "age_seconds": age_seconds,
        }

    def save_remote_lookup(self, result: dict[str, object]) -> None:
        self.store.save_symbol_lookups([result])
        matches = result.get("matches")
        if isinstance(matches, list):
            self.upsert_candidates(matches, source="remote_directory")
