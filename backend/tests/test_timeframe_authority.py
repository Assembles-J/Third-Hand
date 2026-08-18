from types import SimpleNamespace

from app.timeframe_authority import TimeframeAuthorityPolicy


def test_daily_technical_input_is_explicit_and_absent_intraday_data_is_not_inferred():
    authority = TimeframeAuthorityPolicy().assess(SimpleNamespace(technical=object()))

    assert authority.formal_technical_timeframe == "daily"
    assert authority.strategic_timeframes == ("weekly", "daily")
    assert authority.position_management_timeframes == ("60m",)
    assert authority.execution_timing_timeframes == ("15m", "5m")
    assert "60m" in authority.unavailable_timeframes
    assert "realtime" not in authority.unavailable_timeframes


def test_missing_daily_technical_input_is_explicitly_unavailable():
    authority = TimeframeAuthorityPolicy().assess(SimpleNamespace(technical=None))

    assert authority.formal_technical_timeframe is None
    assert "daily" in authority.unavailable_timeframes
