from app.portfolio_analysis import assess_holdings


class FakeStore:
    def __init__(self, risk=None):
        self.risk = risk

    def cached_risk(self, _symbol):
        return self.risk

    def personal_rules(self):
        return []


class FakeTechnicalService:
    def assess(self, _symbol):
        return {
            "as_of": "2026-07-28",
            "sample_count": 180,
            "close": 20.0,
            "trend": "down",
            "trend_label": "空头排列",
            "summary": "收盘价位于 20 日均线下方，均线结构为空头排列。",
            "sma20": 22.0,
            "sma60": 25.0,
            "sma20_distance_percent": -9.1,
            "sma60_distance_percent": -20.0,
            "rsi14": 35.0,
            "rsi_state": "中性",
            "macd_histogram": -0.2,
            "macd_state": "动能偏弱",
            "atr14": 1.0,
            "atr_percent": 5.0,
            "drawdown_60d_percent": -18.0,
        }


def test_technical_snapshot_is_structured_for_clients():
    payload = assess_holdings(
        [{"symbol": "600519", "name": "测试股票", "average_cost": 20.0}],
        [{"symbol": "600519", "price": 20.0, "currency": "CNY", "source": "test"}],
        FakeStore(),
        FakeTechnicalService(),
    )

    item = payload["items"][0]
    assert item["technical_snapshot"]["trend_label"] == "空头排列"
    assert item["technical_snapshot"]["atr_percent"] == 5.0
    assert "技术面：空头排列" in item["evidence"][-1]


def test_weak_technical_trigger_is_not_overwritten_by_observe():
    payload = assess_holdings(
        [{"symbol": "600519", "name": "测试股票", "average_cost": 20.0}],
        [{"symbol": "600519", "price": 20.0, "currency": "CNY", "source": "test"}],
        FakeStore(),
        FakeTechnicalService(),
    )

    item = payload["items"][0]
    assert item["action"] == "risk_review"
    assert "中期趋势偏弱" in item["reason"]
