from app.execution_precheck import validate_daily_execution


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


def test_open_still_requires_allowed_action_gate():
    report = _report("OPEN")
    report["data_quality"] = {
        "action_gates": [{"action": "OPEN", "permission": "blocked"}]
    }

    check = validate_daily_execution(report, _quote())

    assert check.allowed is False
    assert check.reason == "execution_action_gate_blocked"
