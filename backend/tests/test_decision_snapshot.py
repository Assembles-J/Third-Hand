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
        {"enabled": True, "horizon": "swing", "thesis": "测试逻辑", "catalysts": ["公告"], "reduce_condition": "测试减仓条件", "max_position_percent": 15, "risk_budget_percent": 3},
    )

    assert snapshot["quote"]["price"] == 20
    assert snapshot["event_evidence"][0]["source_url"] == "https://example.com/source"
    assert snapshot["evidence_completeness_percent"] == 100
    assert "不代表" in snapshot["confidence_definition"]
    assert "仓位" in snapshot["candidate_action"]
    assert snapshot["trade_plan"]["horizon"] == "swing"


def test_portfolio_snapshot_drops_cross_market_regime_instead_of_showing_cn_for_hk():
    snapshot = build_decision_snapshot(
        {"symbol": "01810", "average_cost": 25, "quantity": 200},
        {"price": 26, "source": "test"},
        {"risk_level": "中"},
        {"max_position_percent": 15},
        [],
        "observe",
        market_regime={
            "status": "ready",
            "regime": "supportive",
            "market": "CN",
            "source": "test",
        },
    )

    assert snapshot["market_regime"] is None


def test_portfolio_snapshot_keeps_same_market_regime():
    regime = {
        "status": "ready",
        "regime": "mixed",
        "market": "HK",
        "source": "test",
    }
    snapshot = build_decision_snapshot(
        {"symbol": "01810", "average_cost": 25, "quantity": 200},
        {"price": 26, "source": "test"},
        {"risk_level": "中"},
        {"max_position_percent": 15},
        [],
        "observe",
        market_regime=regime,
    )

    assert snapshot["market_regime"] == regime
