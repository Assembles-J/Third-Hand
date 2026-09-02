from threading import Event, Lock, Thread

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.paper.router import create_paper_schedule_router
from app.bootstrap.v2_routes import _install_paper_ledger_mutation_guard


class _FakeSimulationService:
    def __init__(self) -> None:
        self.restart_calls = 0

    def epochs(self, limit: int = 20):
        return []

    def restart(self, *, initial_cash: float, client_restart_id: str):
        self.restart_calls += 1
        return {
            "status": "restarted",
            "idempotent_replay": False,
            "archived_epoch_id": "epoch-1",
            "epoch": {
                "epoch_id": "epoch-2",
                "sequence": 2,
                "status": "active",
                "started_at": "2026-09-02T12:00:00+08:00",
                "ended_at": None,
                "initial_cash": initial_cash,
                "end_total_equity": None,
                "end_cash": None,
                "end_market_value": None,
                "restart_request_id": client_restart_id,
            },
        }


def test_restart_rejects_while_paper_ledger_is_mutating() -> None:
    service = _FakeSimulationService()
    mutation_lock = Lock()
    app = FastAPI()
    app.include_router(
        create_paper_schedule_router(
            lambda: {},
            simulation_service=service,
            ledger_mutation_lock=mutation_lock,
        )
    )
    client = TestClient(app)

    mutation_lock.acquire()
    try:
        response = client.post(
            "/v1/paper-trading/restart",
            json={"client_restart_id": "restart-1", "initial_cash": 100000},
        )
    finally:
        mutation_lock.release()

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "paper_restart_runtime_busy"
    assert service.restart_calls == 0

    response = client.post(
        "/v1/paper-trading/restart",
        json={"client_restart_id": "restart-1", "initial_cash": 100000},
    )
    assert response.status_code == 200
    assert service.restart_calls == 1


def test_installed_guard_serializes_full_cycle_and_direct_execution() -> None:
    cycle_entered = Event()
    release_cycle = Event()
    execute_entered = Event()

    class FakeApplication:
        pass

    application = FakeApplication()

    def cycle(*args, **kwargs):
        cycle_entered.set()
        release_cycle.wait(timeout=2)
        return {"run": "cycle"}

    def execute(*args, **kwargs):
        execute_entered.set()
        return (0, 0)

    application.run_paper_trading_cycle = cycle
    application.execute_due_paper_decisions = execute
    _install_paper_ledger_mutation_guard(application)

    cycle_thread = Thread(target=lambda: application.run_paper_trading_cycle([]))
    execute_thread = Thread(target=lambda: application.execute_due_paper_decisions([], {}))
    cycle_thread.start()
    assert cycle_entered.wait(timeout=1)
    execute_thread.start()

    assert not execute_entered.wait(timeout=0.05)
    release_cycle.set()
    cycle_thread.join(timeout=1)
    execute_thread.join(timeout=1)
    assert execute_entered.is_set()
