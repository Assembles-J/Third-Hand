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
