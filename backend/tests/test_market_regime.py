from app.market_regime import MarketRegimeService


class _Series:
    def __init__(self, values): self.values = values
    def tolist(self): return self.values


class _Frame:
    def __init__(self, values): self.index = list(range(len(values))); self.values = values
    def __getitem__(self, _key): return _Series(self.values)


def test_market_regime_classifies_aligned_index_trends_as_supportive():
    prices = list(range(100, 170))
    service = MarketRegimeService(lambda _symbol: _Frame(prices))

    result = service.assess()

    assert result["status"] == "ready"
    assert result["regime"] == "supportive"
    assert len(result["indexes"]) == 3
