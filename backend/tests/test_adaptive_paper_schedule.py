from app.domain.trading.adaptive_schedule import adaptive_paper_schedule


def _account(cash: float, market_value: float, symbols=("600519",)) -> dict[str, object]:
    return {
        "available_cash": cash,
        "market_value": market_value,
        "total_equity": cash + market_value,
        "positions": [{"symbol": symbol, "quantity": 100} for symbol in symbols],
    }


def test_full_focus_disables_candidate_scan_and_keeps_due_symbols():
    plan = adaptive_paper_schedule(
        _account(4_000, 96_000),
        configured_interval_seconds=600,
        pending_symbols=("000001",),
    )

    assert plan.mode == "FULL_FOCUS"
    assert plan.review_interval_seconds == 300
    assert plan.candidate_scan_enabled is False
    assert plan.candidate_scan_interval_seconds is None
    assert plan.holding_research_priority == "L4"
    assert plan.focus_symbols == ("600519", "000001")
    assert plan.cash_ratio == 0.04


def test_holding_focus_reviews_holdings_frequently_but_scans_candidates_less_often():
    plan = adaptive_paper_schedule(
        _account(15_000, 85_000),
        configured_interval_seconds=600,
    )

    assert plan.mode == "HOLDING_FOCUS"
    assert plan.review_interval_seconds == 300
    assert plan.candidate_scan_enabled is True
    assert plan.candidate_scan_interval_seconds == 1800
    assert plan.holding_research_priority == "L3"


def test_discovery_respects_configured_interval_and_keeps_candidate_scan_enabled():
    plan = adaptive_paper_schedule(
        _account(60_000, 40_000),
        configured_interval_seconds=900,
    )

    assert plan.mode == "DISCOVERY"
    assert plan.review_interval_seconds == 900
    assert plan.candidate_scan_interval_seconds == 900
    assert plan.candidate_scan_enabled is True
    assert plan.holding_research_priority == "L2"


def test_empty_account_remains_discovery_without_focus_symbols():
    plan = adaptive_paper_schedule(
        {"available_cash": 100_000, "market_value": 0, "total_equity": 100_000, "positions": []},
        configured_interval_seconds=600,
    )

    assert plan.mode == "DISCOVERY"
    assert plan.focus_symbols == ()
    assert plan.holding_research_priority == "L1"
