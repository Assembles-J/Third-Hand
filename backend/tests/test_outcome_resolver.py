from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
import sqlite3
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.application_services.evaluation import OutcomeResolver
from app.domain.evaluation import ActionOutcomeClass, ExecutionDisposition, OutcomeStatus
from app.domain.experiment import ExperimentUniverseSnapshot
from app.infrastructure.database.evaluation_outcome_repository import EvaluationOutcomeRepository
from app.trading_calendar import TradingCalendarService


TZ = ZoneInfo("Asia/Shanghai")
SESSIONS = (
    "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
    "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16",
    "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23",
    "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30",
    "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06",
)


UNIVERSE = ExperimentUniverseSnapshot(
    universe_snapshot_id="formal-swing-v1-forward:1.0.0:universe",
    experiment_id="formal-swing-v1-forward",
    experiment_version="1.0.0",
    universe_policy_version="explicit-forward-universe-v1",
    captured_at=datetime(2026, 1, 5, 9, 0, tzinfo=TZ),
    members=({"symbol": "600519", "market": "CN"},),
)


def _experiment():
    return SimpleNamespace(
        experiment_id="formal-swing-v1-forward",
        experiment_version="1.0.0",
        outcome_policy_version="1.0.0",
        universe_policy_version=UNIVERSE.universe_policy_version,
        universe_snapshot_id=UNIVERSE.universe_snapshot_id,
        universe_snapshot_hash=UNIVERSE.snapshot_hash,
        universe_snapshot=UNIVERSE,
    )


class FakeCalendar:
    def latest_session_date(self, market, moment):
        eligible = [item for item in SESSIONS if item <= moment.date().isoformat()]
        return eligible[-1] if eligible else None

    def latest_completed_session_date(self, market, moment):
        eligible = [item for item in SESSIONS if item <= moment.date().isoformat()]
        return eligible[-1] if eligible else None

    def session_dates(self, market, start, end):
        return [item for item in SESSIONS if start <= item <= end]

    def session_close(self, market, session_date):
        day = datetime.fromisoformat(session_date).date()
        return datetime.combine(day, time(15, 0), tzinfo=TZ)


class FakeSource:
    def __init__(self, *, action="BUY", price=Decimal("100")):
        self.report = {
            "decision_id": "d1",
            "context_id": "c1",
            "symbol": "600519",
            "generated_at": datetime(2026, 1, 5, 10, 0, tzinfo=TZ),
            "formal_action": action,
            "input_hash": "frozen-input",
            "market_price": str(price) if price is not None else None,
            "sizing": {
                "status": "ready",
                "execution_disposition": "ready",
                "suggested_quantity": 100,
                "max_executable_quantity": 100,
                "blocked_reasons": [],
            },
        }
        self.context = {
            "symbol": "600519",
            "quote": {"price": str(price)} if price is not None else None,
            "instrument": {"market": "CN"},
            "market_regime": {"regime": "range"},
        }
        self.bars = []
        self.fills = []
        self.deferral = None
        self.episodes = {}
        self.episode_fills = []
        self.extra_reports = {}

    def decision_bundle(self, decision_id):
        return {"report": self.report, "context": self.context}

    def decision_report(self, decision_id):
        if decision_id == self.report["decision_id"]:
            return self.report
        return self.extra_reports.get(decision_id)

    def daily_bars_between(self, symbol, start, end):
        return tuple(item for item in self.bars if start <= item["trading_date"] <= end)

    def fills_for_decision(self, decision_id):
        return tuple(item for item in self.fills if item.get("decision_id") == decision_id)

    def deferral_for_decision(self, decision_id):
        if self.deferral and self.deferral.get("decision_id") == decision_id:
            return self.deferral
        return None

    def position_episode(self, episode_id):
        return self.episodes.get(episode_id)

    def fills_for_episode(self, symbol, opened_at, closed_at):
        return tuple(self.episode_fills)


def bar(day, close, high=None, low=None, open_=None, *, adjustment="qfq"):
    close = Decimal(str(close))
    return {
        "trading_date": day,
        "open": str(open_ if open_ is not None else close),
        "close": str(close),
        "high": str(high if high is not None else close),
        "low": str(low if low is not None else close),
        "adjustment": adjustment,
        "source": "local-test",
        "updated_at": f"{day}T16:00:00+08:00",
    }


def test_decision_resolver_uses_strictly_future_observable_sessions_and_local_bars():
    source = FakeSource()
    source.bars = [
        bar("2026-01-05", 999, high=1200, low=1),
        bar("2026-01-06", 101, high=102, low=99),
        # 2026-01-07 deliberately absent: non-observable/suspended.
        bar("2026-01-08", 102, high=105, low=98),
        bar("2026-01-09", 103, high=104, low=100),
    ]
    source.fills = [{
        "id": "fill-1", "decision_id": "d1", "side": "BUY", "quantity": 100,
        "price": 100, "fee": 5, "execution_quote_at": "2026-01-05T10:01:00+08:00",
        "fill_price_mode": "NEXT_ELIGIBLE_OBSERVED_QUOTE",
        "executed_at": "2026-01-05T10:01:00+08:00",
    }]
    result = OutcomeResolver(source, trading_calendar=FakeCalendar()).resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 1, 30, 16, 0, tzinfo=TZ)
    )

    h3 = result.decision_outcomes[0]
    assert h3.outcome_status == OutcomeStatus.RESOLVED
    assert h3.observation_end.date().isoformat() == "2026-01-09"
    assert h3.forward_return == Decimal("0.03")
    assert h3.mfe == Decimal("0.05")
    assert h3.mae == Decimal("-0.02")
    assert h3.action_outcome_class == ActionOutcomeClass.FAVORABLE
    assert result.execution_outcome.execution_disposition == ExecutionDisposition.EXECUTED
    assert result.execution_outcome.fill_ids == ("fill-1",)


def test_incomplete_window_stays_pending_instead_of_scoring_missing_days():
    source = FakeSource()
    source.bars = [bar("2026-01-06", 101), bar("2026-01-08", 102)]
    result = OutcomeResolver(source, trading_calendar=FakeCalendar()).resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 1, 8, 16, 0, tzinfo=TZ)
    )
    assert result.decision_outcomes[0].outcome_status == OutcomeStatus.PENDING
    assert result.decision_outcomes[0].forward_return is None


def test_missing_reference_price_is_terminal_insufficient_without_fake_price():
    source = FakeSource(price=None)
    result = OutcomeResolver(source, trading_calendar=FakeCalendar()).resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 1, 5, 12, 0, tzinfo=TZ)
    )
    h3 = result.decision_outcomes[0]
    assert h3.outcome_status == OutcomeStatus.INSUFFICIENT_DATA
    assert h3.reference_price is None
    assert h3.outcome_reason_codes == ("reference_price_unavailable",)


def test_invalid_local_bar_fails_closed_instead_of_becoming_a_suspension():
    source = FakeSource()
    source.bars = [bar("2026-01-06", 101), bar("2026-01-07", 102, adjustment="raw")]
    result = OutcomeResolver(source, trading_calendar=FakeCalendar()).resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 1, 30, 16, 0, tzinfo=TZ)
    )
    h3 = result.decision_outcomes[0]
    assert h3.outcome_status == OutcomeStatus.INSUFFICIENT_DATA
    assert h3.outcome_reason_codes == ("market_bar_invalid_or_adjustment_mismatch",)


def test_execution_attribution_uses_persisted_deferral_and_no_target_quantity_fallback():
    source = FakeSource(action="EXIT")
    source.report["sizing"] = {
        "status": "ready", "execution_disposition": "deferred_t1",
        "suggested_quantity": 100, "target_quantity": 0, "max_executable_quantity": 0,
        "blocked_reasons": [],
    }
    source.deferral = {
        "decision_id": "d1", "state": "active", "reason_code": "LOT_LOCKED_T1",
        "requested_quantity": 100, "max_executable_quantity": 0,
    }
    execution = OutcomeResolver(source, trading_calendar=FakeCalendar()).resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 1, 5, 12, 0, tzinfo=TZ)
    ).execution_outcome
    assert execution.execution_disposition == ExecutionDisposition.DEFERRED
    assert execution.requested_quantity == 100
    assert execution.executed_quantity == 0
    assert execution.deferral_id == "d1"


def test_closed_episode_uses_fill_economics_and_only_full_session_extrema():
    source = FakeSource()
    opened = datetime(2026, 1, 5, 10, 0, tzinfo=TZ)
    closed = datetime(2026, 1, 9, 14, 0, tzinfo=TZ)
    source.episodes["ep1"] = {
        "episode_id": "ep1", "symbol": "600519", "entry_price": 100,
        "opened_at": opened.isoformat(), "closed_at": closed.isoformat(),
    }
    source.episode_fills = [
        {"id": "b1", "decision_id": "buy-d", "side": "BUY", "quantity": 10,
         "price": 100, "fee": 1, "execution_quote_at": "2026-01-05T10:00:00+08:00",
         "fill_price_mode": "NEXT_ELIGIBLE_OBSERVED_QUOTE",
         "executed_at": "2026-01-05T10:00:00+08:00"},
        {"id": "s1", "decision_id": "exit-d", "side": "SELL", "quantity": 10,
         "price": 110, "fee": 1, "execution_quote_at": "2026-01-09T14:00:00+08:00",
         "fill_price_mode": "NEXT_ELIGIBLE_OBSERVED_QUOTE",
         "executed_at": "2026-01-09T14:00:00+08:00"},
    ]
    source.extra_reports = {
        "buy-d": {"formal_action": "BUY"},
        "exit-d": {"formal_action": "EXIT"},
    }
    source.bars = [
        bar("2026-01-06", 105, high=115, low=98),
        bar("2026-01-07", 100, high=106, low=95),
        bar("2026-01-08", 108, high=112, low=99),
    ]
    outcome = OutcomeResolver(source, trading_calendar=FakeCalendar()).resolve_episode(
        _experiment(), "ep1", as_of=datetime(2026, 1, 9, 16, 0, tzinfo=TZ)
    )
    assert outcome.outcome_status == OutcomeStatus.RESOLVED
    assert outcome.gross_return == Decimal("0.1")
    assert outcome.net_return == Decimal("0.098")
    assert outcome.realized_pnl == Decimal("98")
    assert outcome.slippage == 0
    assert outcome.mfe == Decimal("0.15")
    assert outcome.mae == Decimal("-0.05")
    assert outcome.entry_decision_ids == ("buy-d",)
    assert outcome.position_decision_ids == ("exit-d",)


class SQLiteStore:
    def __init__(self, path):
        self.path = path

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def test_terminal_outcome_repository_is_append_only_and_pending_is_not_persisted(tmp_path):
    source = FakeSource()
    source.bars = [bar("2026-01-06", 101), bar("2026-01-07", 102), bar("2026-01-08", 103)]
    repo = EvaluationOutcomeRepository(SQLiteStore(tmp_path / "eval.db"))
    resolver = OutcomeResolver(source, trading_calendar=FakeCalendar(), outcome_repository=repo)
    first = resolver.resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 1, 30, 16, 0, tzinfo=TZ)
    ).decision_outcomes[0]
    second = resolver.resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 2, 3, 16, 0, tzinfo=TZ)
    ).decision_outcomes[0]
    assert second.contract_hash == first.contract_hash

    pending = resolver.resolve_decision(
        _experiment(), "d1", as_of=datetime(2026, 1, 5, 12, 0, tzinfo=TZ)
    ).decision_outcomes[-1]
    if pending.outcome_status == OutcomeStatus.PENDING:
        with pytest.raises(ValueError, match="PENDING"):
            repo.save_decision(pending)


def test_official_session_close_comes_from_exchange_calendar():
    close = TradingCalendarService().session_close("CN", "2026-01-05")
    assert close is not None
    assert close.isoformat() == "2026-01-05T15:00:00+08:00"

def test_resolver_rejects_source_outside_frozen_experiment_universe():
    source = FakeSource()
    source.report["symbol"] = "000001"
    source.context["symbol"] = "000001"
    source.context["instrument"] = {"market": "CN"}
    with pytest.raises(ValueError, match="outside frozen experiment universe"):
        OutcomeResolver(source, trading_calendar=FakeCalendar()).resolve_decision(
            _experiment(), "d1", as_of=datetime(2026, 1, 30, 16, 0, tzinfo=TZ)
        )

