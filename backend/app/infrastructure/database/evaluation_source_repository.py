"""Read-only adapters exposing persisted facts to N3 OutcomeResolver.

This repository intentionally owns no refresh/provider behavior. It only reads
facts that already exist in the local ThirdHand SQLite database.
"""
from __future__ import annotations

import json
from datetime import datetime


class EvaluationSourceRepository:
    def __init__(self, store) -> None:
        self.store = store

    def decision_bundle(self, decision_id: str) -> dict[str, object] | None:
        report = self.store.decision_report(str(decision_id))
        if not report:
            return None
        context_id = str(report.get("context_id") or "").strip()
        context = self.store.decision_context(context_id) if context_id else None
        if not context:
            return None
        return {"report": report, "context": context}

    def decision_report(self, decision_id: str) -> dict[str, object] | None:
        return self.store.decision_report(str(decision_id))

    def daily_bars_between(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        *,
        limit: int = 4000,
    ) -> tuple[dict[str, object], ...]:
        """Read normalized daily OHLC rows from SQLite only; never refresh."""
        with self.store._connect() as connection:
            rows = connection.execute(
                """
                SELECT trading_date,open,close,high,low,volume,amount,
                       adjustment,source,updated_at
                FROM daily_price_cache
                WHERE symbol=? AND trading_date>=? AND trading_date<=?
                ORDER BY trading_date ASC LIMIT ?
                """,
                (
                    str(symbol).strip().upper(),
                    str(start_date),
                    str(end_date),
                    max(1, int(limit)),
                ),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def fills_for_decision(self, decision_id: str) -> tuple[dict[str, object], ...]:
        with self.store._connect() as connection:
            rows = connection.execute(
                """
                SELECT id,symbol,side,quantity,price,fee,decision_id,reason,status,
                       execution_quote_at,execution_quote_source,fill_price_mode,executed_at
                FROM paper_trading_logs
                WHERE decision_id=? AND status='executed' AND side IN ('BUY','SELL')
                ORDER BY executed_at ASC,id ASC
                """,
                (str(decision_id),),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def deferral_for_decision(self, decision_id: str) -> dict[str, object] | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_execution_deferrals WHERE decision_id=?",
                (str(decision_id),),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        raw_detail = item.get("detail")
        if isinstance(raw_detail, str):
            try:
                item["detail"] = json.loads(raw_detail)
            except json.JSONDecodeError:
                pass
        return item

    def position_episode(self, position_episode_id: str) -> dict[str, object] | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_position_episodes WHERE episode_id=?",
                (str(position_episode_id),),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        for field in (
            "entry_risk_state",
            "entry_technical_state",
            "entry_market_regime",
            "entry_event_state",
            "detail",
        ):
            raw = item.get(field)
            if isinstance(raw, str):
                try:
                    item[field] = json.loads(raw)
                except json.JSONDecodeError:
                    pass
        return item

    def fills_for_episode(
        self,
        symbol: str,
        opened_at: datetime,
        closed_at: datetime,
    ) -> tuple[dict[str, object], ...]:
        """Read executed fills inside one symbol's persisted episode boundaries."""
        with self.store._connect() as connection:
            rows = connection.execute(
                """
                SELECT id,symbol,side,quantity,price,fee,decision_id,reason,status,
                       execution_quote_at,execution_quote_source,fill_price_mode,executed_at
                FROM paper_trading_logs
                WHERE symbol=? AND status='executed' AND side IN ('BUY','SELL')
                  AND executed_at>=? AND executed_at<=?
                ORDER BY executed_at ASC,id ASC
                """,
                (
                    str(symbol).strip().upper(),
                    opened_at.isoformat(),
                    closed_at.isoformat(),
                ),
            ).fetchall()
        return tuple(dict(row) for row in rows)


__all__ = ["EvaluationSourceRepository"]
