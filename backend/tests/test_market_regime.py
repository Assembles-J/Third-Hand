from app.market_regime import MarketRegimeService, regime_market


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
    assert result["market"] == "CN"
    assert result["benchmark_symbols"] == ["sh000001", "sh000300", "sz399006"]
    assert len(result["indexes"]) == 3


def test_hk_regime_never_falls_back_to_a_share_indexes_without_provider():
    calls = []

    def fetcher(symbol):
        calls.append(symbol)
        return _Frame(list(range(100, 170)))

    result = MarketRegimeService(fetcher).assess("HK")

    assert result["status"] == "unavailable"
    assert result["regime"] == "unknown"
    assert result["market"] == "HK"
    assert result["benchmark_symbols"] == ["HSI", "HSTECH"]
    assert result["indexes"] == []
    assert calls == []
    assert "不会回退" in result["note"]


def test_legacy_market_regime_is_only_recognized_as_cn_when_shape_proves_it():
    legacy_cn = {
        "status": "ready",
        "regime": "mixed",
        "source": "fixture",
        "indexes": [{"symbol": "sh000300"}],
    }
    ambiguous = {"status": "ready", "regime": "mixed", "source": "fixture"}

    assert regime_market(legacy_cn) == "CN"
    assert regime_market(ambiguous) is None
