"""Install a bounded compatibility guard for legacy realtime quote history.

Third-Hand's normalized historical price stores are ``intraday_price_cache`` and
``daily_price_cache``.  ``market_quote_history`` is retained only for legacy
compatibility, and must never grow as an unbounded archive of full provider JSON
snapshots.
"""
from __future__ import annotations

import sqlite3

from app.storage import PortfolioStore


TRIGGER_NAME = "cap_market_quote_history_per_symbol"


def install_quote_history_guard(store: PortfolioStore) -> None:
    """Keep at most the newest raw quote row for each symbol.

    The existing save path inserts into ``market_quote_cache`` first and then
    appends to ``market_quote_history``.  Deleting the previous compatibility row
    immediately before the insert preserves a latest-row view for old admin or
    diagnostic readers while making storage usage O(symbols), not O(refreshes).
    """
    with store._connect() as connection:  # noqa: SLF001 - startup maintenance boundary
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {TRIGGER_NAME}
            BEFORE INSERT ON market_quote_history
            FOR EACH ROW
            BEGIN
                DELETE FROM market_quote_history WHERE symbol = NEW.symbol;
            END
            """
        )


def main() -> int:
    store = PortfolioStore()
    install_quote_history_guard(store)
    with sqlite3.connect(store.database_path) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name=?",
            (TRIGGER_NAME,),
        ).fetchone()
    if row is None:
        raise RuntimeError("quote history guard was not installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
