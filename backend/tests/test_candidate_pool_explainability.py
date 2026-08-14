from app.candidate_selection import select_candidates
from app.paper_runtime import candidate_pool_audit


def test_candidate_pool_audit_exposes_selection_algorithm_and_lineage():
    selection = select_candidates(
        ["000001", "000002", "600519", "300750"],
        position_symbols=["600519"],
        limit=3,
        rotation_key="2026-08-14",
    )

    audit = candidate_pool_audit(
        selection,
        requested_symbols=(),
        decision_symbols=selection.symbols,
        due_symbols=(),
    )

    assert audit["eligible_count"] == 4
    assert audit["requested_limit"] == 3
    assert audit["selected_count"] == 3
    assert audit["selection_algorithm"] == "paper_positions_first_then_sha256_deterministic_rotation"
    assert audit["rotation_material"] == f"{selection.selection_version}|2026-08-14|<symbol>"
    assert "news" in audit["selection_independent_of"]
    assert "llm_output" in audit["selection_independent_of"]
    assert audit["selected_items"][0] == {
        "symbol": "600519",
        "rank": 1,
        "reason": "paper_position_risk_monitor",
    }
    assert all(item["reason"] in {"paper_position_risk_monitor", "deterministic_rotation"} for item in audit["selected_items"])
