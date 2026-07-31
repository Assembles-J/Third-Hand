from app.impact_graph import build_impact_graph


class FakeStore:
    def cached_risk(self, symbol):
        return {
            "symbol": symbol,
            "risk_level": "中",
            "historical_downside_probability": 12.5,
            "annualized_volatility_percent": 31.2,
            "as_of": "2026-07-30",
        }

    def cached_content(self, symbols, limit=30):
        return [{
            "id": "announcement-1", "title": "回购进展公告", "related_symbols": symbols,
            "explanation": "正式公告", "source_url": "https://example.com/a", "confidence": 0.95,
            "ai_analysis": {"impact": "positive", "summary": "回购正在推进。"},
        }]


def test_impact_graph_links_market_risk_and_source_event_to_holding():
    graph = build_impact_graph(
        [{"symbol": "600519", "name": "测试股票", "quantity": 100, "average_cost": 18}],
        [{"symbol": "600519", "price": 20, "volume": 1000, "source": "test"}],
        FakeStore(),
    )

    assert {item["kind"] for item in graph["nodes"]} == {"holding", "market", "risk", "event"}
    assert any(edge["direction"] == "positive" for edge in graph["edges"])
    assert graph["disclaimer"]
