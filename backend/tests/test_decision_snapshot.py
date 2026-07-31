from app.decision_snapshot import build_decision_snapshot


def test_decision_snapshot_keeps_sources_and_separates_evidence_confidence():
    snapshot = build_decision_snapshot(
        {"symbol": "600519", "average_cost": 18, "quantity": 100},
        {"price": 20, "volume": 1000, "source": "test", "freshness_note": "snapshot"},
        {"risk_level": "中"},
        {"max_position_percent": 15},
        [{
            "id": "notice-1", "title": "回购公告", "related_symbols": ["600519"],
            "source_url": "https://example.com/source", "explanation": "正式公告",
            "ai_analysis": {"impact": "positive", "summary": "回购推进"},
        }],
        "risk_review",
    )

    assert snapshot["quote"]["price"] == 20
    assert snapshot["event_evidence"][0]["source_url"] == "https://example.com/source"
    assert snapshot["evidence_completeness_percent"] == 100
    assert "不代表" in snapshot["confidence_definition"]
    assert "仓位" in snapshot["candidate_action"]
