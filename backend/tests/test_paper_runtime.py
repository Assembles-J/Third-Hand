from app import decision_config as config
from app.candidate_selection import select_candidates
from app.paper_runtime import (
    latest_current_version_decision_report,
    report_matches_current_selection,
    runtime_scope,
)


def test_requested_scope_can_only_narrow_not_inject_candidates_or_due_items():
    selection = select_candidates(
        ["600001", "600002", "600003"],
        position_symbols=["600003"],
        limit=2,
        rotation_key="2026-08-14",
    )

    decision, due, runtime = runtime_scope(
        selection,
        requested_symbols=["600001", "600003", "999999"],
        pending_symbols=["600002", "888888"],
    )

    assert "999999" not in decision
    assert "999999" not in runtime
    assert "888888" not in due
    assert "888888" not in runtime
    assert set(runtime).issubset({*selection.symbols, "600002"})


def test_due_historical_decision_survives_new_rotation_when_in_execution_scope():
    selection = select_candidates(
        ["600001", "600002", "600003", "600004"],
        limit=2,
        rotation_key="2026-08-14",
    )
    old_due = next(symbol for symbol in ["600001", "600002", "600003", "600004"] if symbol not in selection.symbols)

    decision, due, runtime = runtime_scope(
        selection,
        requested_symbols=[*selection.symbols, old_due],
        pending_symbols=[old_due],
    )

    assert old_due not in decision
    assert due == (old_due,)
    assert old_due in runtime


def test_report_reuse_requires_same_candidate_and_policy_lineage():
    selection = select_candidates(["600001", "600002"], limit=1, rotation_key="2026-08-14")
    report = {
        "policy_version": "policy-v2",
        "candidate_selection_version": selection.selection_version,
        "candidate_pool_hash": selection.candidate_pool_hash,
        "candidate_rotation_key": selection.rotation_key,
    }

    assert report_matches_current_selection(report, selection, policy_version="policy-v2")
    assert not report_matches_current_selection({**report, "policy_version": "policy-v1"}, selection, policy_version="policy-v2")
    assert not report_matches_current_selection({**report, "candidate_pool_hash": "old"}, selection, policy_version="policy-v2")


def test_newer_manual_report_does_not_mask_latest_formal_paper_report():
    formal = {
        "decision_id": "formal",
        "policy_version": "policy-v2",
        "candidate_selection_version": config.CANDIDATE_SELECTION_VERSION,
    }
    manual = {
        "decision_id": "manual",
        "policy_version": "policy-v2",
        "candidate_selection_version": None,
    }

    class Store:
        @staticmethod
        def decision_reports(_symbol, _limit):
            return [manual, formal]

    resolved = latest_current_version_decision_report(Store(), "600001", policy_version="policy-v2")
    assert resolved is formal
