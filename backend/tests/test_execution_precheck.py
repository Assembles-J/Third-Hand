from datetime import datetime

from app.execution_precheck import execution_quote_observed_at, precheck_fill, validate_daily_execution


def _report(action: str = "OPEN", market_as_of: str = "2026-08-17T10:04:00+08:00") -> dict[str, object]:
    return {
        "action": action,
        "market_as_of": market_as_of,
        "generated_at": "2026-08-17T10:04:05+08:00",
        "data_quality": {
            "action_gates": [
                {"action": "OPEN", "permission": "allowed"},
                {"action": "ADD", "permission": "allowed"},
            ]
        },
    }


def _quote(as_of: str = "2026-08-17T10:14:00+08:00") -> dict[str, object]:
    return {
        "price": 10.5,
        "as_of": as_of,
        "retrieved_at": "2026-08-17T10:14:01+08:00",
    }


def test_open_can_fill_on_later_quote_in_same_trading_day():
    check = validate_daily_execution(_report("OPEN"), _quote())

    assert check.allowed is True
    assert check.reason is None


def test_reduce_can_fill_on_later_quote_in_same_trading_day():
    # T+1 sell availability is enforced by the paper ledger.  An old sellable
    # position may therefore reduce on a later quote in the same trading day.
    check = validate_daily_execution(_report("REDUCE"), _quote())

    assert check.allowed is True


def test_same_input_quote_cannot_fill_same_cycle():
    check = validate_daily_execution(
        _report("OPEN", "2026-08-17T10:04:00+08:00"),
        _quote("2026-08-17T10:04:00+08:00"),
    )

    assert check.allowed is False
    assert check.reason == "execution_not_due_later_quote"


def test_earlier_quote_cannot_fill():
    check = validate_daily_execution(
        _report("OPEN", "2026-08-17T10:04:00+08:00"),
        _quote("2026-08-17T10:03:59+08:00"),
    )

    assert check.allowed is False
    assert check.reason == "execution_not_due_later_quote"


def test_date_only_market_as_of_uses_retrieved_timestamp_for_ordering():
    report = _report("OPEN", "2026-08-17")
    quote = {
        "price": 10.5,
        "as_of": "2026-08-17",
        "retrieved_at": "2026-08-17T10:14:01+08:00",
    }

    check = validate_daily_execution(report, quote)

    assert check.allowed is True


def test_execution_quote_audit_uses_retrieved_at_when_as_of_is_date_only():
    quote = {
        "price": 10.5,
        "as_of": "2026-08-17",
        "retrieved_at": "2026-08-17T10:14:01+08:00",
    }

    assert execution_quote_observed_at(quote) == "2026-08-17T10:14:01+08:00"


def test_execution_quote_audit_prefers_precise_provider_time():
    quote = {
        "price": 10.5,
        "as_of": "2026-08-17T10:14:00+08:00",
        "retrieved_at": "2026-08-17T10:14:01+08:00",
    }

    assert execution_quote_observed_at(quote) == "2026-08-17T10:14:00+08:00"


def test_open_still_requires_allowed_action_gate():
    report = _report("OPEN")
    report["data_quality"] = {
        "action_gates": [{"action": "OPEN", "permission": "blocked"}]
    }

    check = validate_daily_execution(report, _quote())

    assert check.allowed is False
    assert check.reason == "execution_action_gate_blocked"


def test_formal_buy_uses_the_legacy_open_gate_during_compatibility_migration():
    report = _report("WATCH")
    report["formal_action"] = "BUY"
    report["data_quality"] = {"action_gates": [{"action": "OPEN", "permission": "blocked"}]}

    check = validate_daily_execution(report, _quote())

    assert check.allowed is False
    assert check.reason == "execution_action_gate_blocked"


def test_execution_waits_for_the_persisted_decision_cooldown():
    report = _report("OPEN")
    report["decision_memory"] = {"cooldown_until": "2026-08-17T10:20:00+08:00"}

    check = validate_daily_execution(report, _quote("2026-08-17T10:14:00+08:00"))

    assert check.allowed is False
    assert check.reason == "execution_cooldown_active"


def test_execution_allows_the_quote_at_the_decision_cooldown_boundary():
    report = _report("OPEN")
    report["decision_memory"] = {"cooldown_until": "2026-08-17T10:14:00+08:00"}

    assert validate_daily_execution(report, _quote("2026-08-17T10:14:00+08:00")).allowed is True


class _Calendar:
    def __init__(self, *, now_open: bool = True, quote_open: bool = True) -> None:
        self.now_open, self.quote_open = now_open, quote_open

    def is_symbol_market_open(self, _symbol, *, moment):
        return self.quote_open if moment.hour == 10 and moment.minute == 14 else self.now_open


def test_live_fill_precheck_rejects_a_stale_quote_even_when_decision_ordering_is_valid():
    check = precheck_fill(
        _report(), _quote(), symbol="600000",
        now=datetime.fromisoformat("2026-08-17T10:30:00+08:00"),
        calendar=_Calendar(), max_quote_age_seconds=900,
    )

    assert check.allowed is False
    assert check.reason == "execution_quote_stale"


def test_live_fill_precheck_requires_both_current_and_quote_exchange_sessions():
    quote_outside = precheck_fill(
        _report(), _quote(), symbol="600000",
        now=datetime.fromisoformat("2026-08-17T10:15:00+08:00"),
        calendar=_Calendar(quote_open=False), max_quote_age_seconds=900,
    )
    market_closed = precheck_fill(
        _report(), _quote(), symbol="600000",
        now=datetime.fromisoformat("2026-08-17T10:15:00+08:00"),
        calendar=_Calendar(now_open=False), max_quote_age_seconds=900,
    )

    assert quote_outside.reason == "execution_quote_outside_session"
    assert market_closed.reason == "execution_market_closed"
