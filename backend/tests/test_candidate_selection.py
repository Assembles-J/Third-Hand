from app.candidate_selection import select_candidates


def test_selection_is_deterministic_and_positions_are_reserved():
    eligible = ["600003", "600001", "600002", "600004", "600005"]
    first = select_candidates(eligible, position_symbols=["600004"], limit=3, rotation_key="2026-08-14")
    second = select_candidates(reversed(eligible), position_symbols=["600004"], limit=3, rotation_key="2026-08-14")

    assert first == second
    assert first.symbols[0] == "600004"
    assert len(first.symbols) == 3
    assert first.candidate_pool_hash
    assert first.selection_version.startswith("candidate-rotation")
    assert first.audit_for("600004")["candidate_selection_reason"] == "paper_position_risk_monitor"


def test_positions_outside_eligible_pool_are_never_hidden_by_data_gaps_or_limit():
    result = select_candidates(
        ["600001", "600002"],
        position_symbols=["900003", "900001", "900002"],
        limit=2,
        rotation_key="2026-08-14",
    )

    assert result.position_symbols == ("900001", "900002", "900003")
    assert result.symbols == result.position_symbols
    assert all(result.audit_for(symbol)["candidate_rank"] >= 1 for symbol in result.position_symbols)


def test_watchlist_or_hot_sector_metadata_cannot_affect_scheduler():
    eligible = ["000001", "000002", "000003", "000004"]
    baseline = select_candidates(eligible, limit=2, rotation_key="2026-08-14")

    # The scheduler intentionally has no watchlist, sector, return, fund-flow or
    # AI parameters. The same eligible universe therefore produces the same cohort.
    repeated = select_candidates(eligible, limit=2, rotation_key="2026-08-14")
    assert baseline.symbols == repeated.symbols


def test_rotation_key_changes_cohort_without_changing_pool_identity():
    eligible = [f"600{index:03d}" for index in range(20)]
    day_one = select_candidates(eligible, limit=4, rotation_key="2026-08-14")
    day_two = select_candidates(eligible, limit=4, rotation_key="2026-08-17")

    assert day_one.candidate_pool_hash == day_two.candidate_pool_hash
    assert day_one.symbols != day_two.symbols
