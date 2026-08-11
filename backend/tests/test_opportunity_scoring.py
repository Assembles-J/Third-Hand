from app.opportunity_scoring import score_opportunity


def _bars() -> list[dict]:
    return [{"close": 10 + index * 0.05} for index in range(65)]


def test_confidence_is_evidence_quality_not_upside_likelihood():
    result = score_opportunity(
        quote={"price": 13.3, "volume_ratio": 1.8}, bars=_bars(),
        risk={"status": "ready", "historical_downside_probability": 8, "annualized_volatility_percent": 20},
        sector_change_percent=2.2, sources=["market"],
    )

    assert result["confidence"] >= 90
    assert result["upside_likelihood"] > 50
    assert result["risk_level"] == "低"


def test_missing_history_is_ranked_low_with_explicit_low_confidence():
    result = score_opportunity(
        quote={"price": 10.0}, bars=[{"close": 10.0}] * 3, risk=None,
        sector_change_percent=None, sources=["watchlist"],
    )

    assert result["confidence"] < 50
    assert result["score"] < 60
