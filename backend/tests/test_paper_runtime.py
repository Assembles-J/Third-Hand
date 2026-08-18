import json
from datetime import datetime

from app import decision_config as config
from app.candidate_selection import select_candidates
from app.paper_runtime import (
    due_current_version_review_symbols,
    latest_current_version_decision_report,
    report_matches_current_selection,
    runtime_scope,
)


def _execution_audit() -> dict[str, str]:
    return {"execution_policy_version": config.EXECUTION_POLICY_VERSION}


def test_requested_scope_can_only_narrow_not_inject_candidates_or_due_items():
    selection = select_candidates(
        ["600001", "600002", "600003"],
        position_symbols=["600003"],
        limit=2,
        rotation_key="2026-08-14",
    )

    decision, reviews, due, runtime = runtime_scope(
        selection,
        requested_symbols=["600001", "600003", "999999"],
        pending_symbols=["600002", "888888"],
    )

    assert "999999" not in decision
    assert reviews == ()
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

    decision, reviews, due, runtime = runtime_scope(
        selection,
        requested_symbols=[*selection.symbols, old_due],
        pending_symbols=[old_due],
    )

    assert old_due not in decision
    assert reviews == ()
    assert due == (old_due,)
    assert old_due in runtime


def test_due_review_is_a_decision_obligation_not_an_execution_obligation():
    selection = select_candidates(["600001", "600002"], limit=1, rotation_key="2026-08-14")
    review_symbol = next(symbol for symbol in ["600001", "600002"] if symbol not in selection.symbols)

    decision, reviews, due, runtime = runtime_scope(
        selection,
        requested_symbols=[review_symbol],
        pending_symbols=(),
        review_symbols=[review_symbol],
    )

    assert decision == (review_symbol,)
    assert reviews == (review_symbol,)
    assert due == ()
    assert runtime == (review_symbol,)


def test_due_review_queue_uses_only_latest_current_formal_report(tmp_path):
    from app.storage import PortfolioStore

    store = PortfolioStore(tmp_path / "runtime-review.db")
    current = {
        "policy_version": "policy-v2",
        "candidate_selection_version": config.CANDIDATE_SELECTION_VERSION,
        "audit_versions": _execution_audit(),
        "decision_memory": {"review_after": "2026-08-17T09:00:00+08:00"},
        "evidence": [], "action_candidates": [], "operation_items": [],
    }
    newer_not_due = {
        **current,
        "decision_memory": {"review_after": "2026-08-19T09:00:00+08:00"},
    }
    with store._connect() as connection:
        connection.executemany(
            "INSERT INTO decision_reports VALUES (?,?,?,?,?,?)",
            [
                ("due", "ctx", "600001", "hash", json.dumps(current), "2026-08-17T08:00:00+08:00"),
                ("newer", "ctx", "600001", "hash", json.dumps(newer_not_due), "2026-08-18T08:00:00+08:00"),
                ("review", "ctx", "600002", "hash", json.dumps(current), "2026-08-17T08:00:00+08:00"),
            ],
        )

    assert due_current_version_review_symbols(
        store,
        policy_version="policy-v2",
        now=datetime.fromisoformat("2026-08-18T10:00:00+08:00"),
    ) == ("600002",)


def test_report_reuse_requires_same_candidate_policy_and_execution_lineage():
    selection = select_candidates(["600001", "600002"], limit=1, rotation_key="2026-08-14")
    report = {
        "policy_version": "policy-v2",
        "candidate_selection_version": selection.selection_version,
        "candidate_pool_hash": selection.candidate_pool_hash,
        "candidate_rotation_key": selection.rotation_key,
        "audit_versions": _execution_audit(),
    }

    assert report_matches_current_selection(report, selection, policy_version="policy-v2")
    assert not report_matches_current_selection({**report, "policy_version": "policy-v1"}, selection, policy_version="policy-v2")
    assert not report_matches_current_selection({**report, "candidate_pool_hash": "old"}, selection, policy_version="policy-v2")
    assert not report_matches_current_selection(
        {**report, "audit_versions": {"execution_policy_version": "execution-v1-next-session"}},
        selection,
        policy_version="policy-v2",
    )


def test_newer_manual_report_does_not_mask_latest_formal_paper_report():
    formal = {
        "decision_id": "formal",
        "policy_version": "policy-v2",
        "candidate_selection_version": config.CANDIDATE_SELECTION_VERSION,
        "audit_versions": _execution_audit(),
    }
    manual = {
        "decision_id": "manual",
        "policy_version": "policy-v2",
        "candidate_selection_version": None,
        "audit_versions": _execution_audit(),
    }

    class Store:
        @staticmethod
        def decision_reports(_symbol, _limit):
            return [manual, formal]

    resolved = latest_current_version_decision_report(Store(), "600001", policy_version="policy-v2")
    assert resolved is formal


def test_old_execution_policy_report_is_not_due_under_new_execution_semantics():
    old = {
        "decision_id": "old-execution-policy",
        "policy_version": "policy-v2",
        "candidate_selection_version": config.CANDIDATE_SELECTION_VERSION,
        "audit_versions": {"execution_policy_version": "execution-v1-next-session"},
    }

    class Store:
        @staticmethod
        def decision_reports(_symbol, _limit):
            return [old]

    assert latest_current_version_decision_report(Store(), "600001", policy_version="policy-v2") is None
