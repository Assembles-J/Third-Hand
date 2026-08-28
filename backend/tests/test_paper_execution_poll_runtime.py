from threading import Lock
from types import SimpleNamespace

import app.paper_execution_poll_runtime as runtime


class _Store:
    def __init__(self):
        self.snapshots = 0

    @staticmethod
    def system_settings():
        return {"paper_trading_enabled": True}

    def record_paper_equity_snapshot(self):
        self.snapshots += 1


class _Clock:
    @staticmethod
    def monotonic():
        return 160.0


def test_execution_poll_runs_pending_frozen_decision_without_advancing_analysis_clock(monkeypatch):
    calls = {"original": 0, "execution": 0, "finished": 0}

    def original(_symbols, force=False, allow_when_disabled=False):
        calls["original"] += 1
        return {"executed": 0, "skipped": 0, "run_id": None}

    def execute(symbols, _names, run_id=None):
        calls["execution"] += 1
        assert symbols == ["600001"]
        assert run_id == "poll-run"
        return 1, 0

    module = SimpleNamespace(
        run_paper_trading_cycle=original,
        store=_Store(),
        action_policy_engine=SimpleNamespace(version="policy-v2"),
        adaptive_paper_schedule_state=lambda: {"review_interval_seconds": 300},
        last_paper_trading_run_at=100.0,
        MARKET_REFRESH_INTERVAL_SECONDS=60,
        time=_Clock(),
        paper_trading_names=lambda symbols: {symbol: symbol for symbol in symbols},
        _create_simulation_run=lambda *_args: "poll-run",
        execute_due_paper_decisions=execute,
        paper_trading_state_lock=Lock(),
        paper_trading_state={},
        beijing_now=lambda: "2026-08-28T15:00:00+08:00",
        _finish_simulation_run=lambda *_args, **_kwargs: calls.__setitem__("finished", calls["finished"] + 1),
    )
    monkeypatch.setattr(runtime, "pending_current_version_decision_symbols", lambda *_args, **_kwargs: ("600001",))

    runtime.install(module)
    result = module.run_paper_trading_cycle(["600001"])

    assert result == {"executed": 1, "skipped": 0, "run_id": "poll-run"}
    assert calls == {"original": 0, "execution": 1, "finished": 1}
    assert module.last_paper_trading_run_at == 100.0
    assert module.last_paper_execution_poll_at == 160.0
    assert module.store.snapshots == 1
    assert module.paper_trading_state["last_status"] == "execution_poll_completed"


def test_execution_poll_does_not_bypass_full_review_when_analysis_is_due(monkeypatch):
    calls = {"original": 0}

    def original(_symbols, force=False, allow_when_disabled=False):
        calls["original"] += 1
        return {"executed": 0, "skipped": 0, "run_id": "full"}

    module = SimpleNamespace(
        run_paper_trading_cycle=original,
        store=_Store(),
        action_policy_engine=SimpleNamespace(version="policy-v2"),
        adaptive_paper_schedule_state=lambda: {"review_interval_seconds": 60},
        last_paper_trading_run_at=100.0,
        MARKET_REFRESH_INTERVAL_SECONDS=60,
        time=_Clock(),
    )
    monkeypatch.setattr(runtime, "pending_current_version_decision_symbols", lambda *_args, **_kwargs: ("600001",))

    runtime.install(module)
    result = module.run_paper_trading_cycle(["600001"])

    assert result["run_id"] == "full"
    assert calls["original"] == 1
