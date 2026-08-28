from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app import hithink_finance as hithink


def _response(data=None, *, code=0, message="ok", request_id="req-1"):
    return httpx.Response(
        200,
        json={
            "code": code,
            "message": message,
            "request_id": request_id,
            "data": data or {},
        },
    )


def test_provider_is_opt_in_and_requires_key():
    disabled = hithink.HiThinkFinanceClient(enabled=False, api_key="secret")
    missing_key = hithink.HiThinkFinanceClient(enabled=True, api_key="")

    assert disabled.available is False
    assert missing_key.available is False


def test_symbol_search_is_bounded_and_key_stays_in_header(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _response({
            "item": [{
                "thscode": "600519.SH",
                "ticker": "600519",
                "name": "贵州茅台",
                "exchange": "SH",
                "asset_type": "a-share",
                "currency": "CNY",
            }]
        })

    monkeypatch.setattr(hithink.httpx, "get", fake_get)
    client = hithink.HiThinkFinanceClient(enabled=True, api_key="secret-key")

    result = client.search("贵州茅台", limit=50)

    assert result[0]["ticker"] == "600519"
    assert calls[0][0].endswith("/api/meta/tickers/search")
    assert calls[0][1]["params"] == {
        "q": "贵州茅台",
        "asset_type": "a-share",
        "limit": 5,
    }
    assert calls[0][1]["headers"] == {"X-api-key": "secret-key"}
    assert "secret-key" not in calls[0][0]


def test_snapshot_always_uses_explicit_thscodes(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/meta/tickers/search"):
            return _response({
                "item": [{
                    "thscode": "600519.SH",
                    "ticker": "600519",
                    "name": "贵州茅台",
                    "exchange": "SH",
                    "asset_type": "a-share",
                    "currency": "CNY",
                }]
            })
        return _response({
            "timestamp": None,
            "total": 1,
            "item": [{
                "thscode": "600519.SH",
                "ticker": "600519",
                "last_price": 1500.0,
                "price_change": 12.0,
                "price_change_ratio_pct": 0.81,
                "open_price": 1490.0,
                "high_price": 1510.0,
                "low_price": 1488.0,
                "prev_price": 1488.0,
                "volume": 1000,
                "turnover": 1_500_000,
            }],
        })

    monkeypatch.setattr(hithink.httpx, "get", fake_get)
    client = hithink.HiThinkFinanceClient(enabled=True, api_key="secret-key")

    quotes = client.quotes(["600519"])

    snapshot_call = next(item for item in calls if item[0].endswith("/api/a-share/prices/snapshot"))
    assert snapshot_call[1]["params"] == {"thscodes": "600519.SH"}
    assert "limit" not in snapshot_call[1]["params"]
    assert "offset" not in snapshot_call[1]["params"]
    assert quotes[0]["symbol"] == "600519"
    assert quotes[0]["name"] == "贵州茅台"
    assert quotes[0]["price"] == 1500.0
    assert quotes[0]["source"] == hithink.SOURCE_NAME


def test_permission_error_does_not_retry(monkeypatch):
    calls = 0

    def fake_get(_url, **_kwargs):
        nonlocal calls
        calls += 1
        return _response({}, code=2003, message="capability denied")

    monkeypatch.setattr(hithink.httpx, "get", fake_get)
    monkeypatch.setattr(hithink.time, "sleep", lambda _seconds: pytest.fail("must not back off for permission errors"))
    client = hithink.HiThinkFinanceClient(enabled=True, api_key="secret-key")

    with pytest.raises(hithink.HiThinkFinanceError) as error:
        client.search("600519")

    assert error.value.code == 2003
    assert calls == 1


def test_rate_limit_has_bounded_retry(monkeypatch):
    calls = 0
    sleeps = []

    def fake_get(_url, **_kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            return _response({}, code=4001, message="rate limited", request_id=f"req-{calls}")
        return _response({
            "item": [{
                "thscode": "600519.SH",
                "ticker": "600519",
                "name": "贵州茅台",
                "exchange": "SH",
                "asset_type": "a-share",
                "currency": "CNY",
            }]
        }, request_id="req-3")

    monkeypatch.setattr(hithink.httpx, "get", fake_get)
    monkeypatch.setattr(hithink.time, "sleep", lambda seconds: sleeps.append(seconds))
    client = hithink.HiThinkFinanceClient(enabled=True, api_key="secret-key")

    result = client.search("600519")

    assert result[0]["thscode"] == "600519.SH"
    assert calls == 3
    assert sleeps == [0.25, 0.5]


def test_historical_uses_single_symbol_daily_forward_adjustment(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/meta/tickers/search"):
            return _response({
                "item": [{
                    "thscode": "000001.SZ",
                    "ticker": "000001",
                    "name": "平安银行",
                    "exchange": "SZ",
                    "asset_type": "a-share",
                    "currency": "CNY",
                }]
            })
        return _response({
            "timestamp": 1787875200000,
            "item": [{
                "date_ms": 1787846400000,
                "open_price": 10.0,
                "high_price": 10.8,
                "low_price": 9.9,
                "close_price": 10.6,
                "volume": 123456,
                "turnover": 1_234_567.8,
            }],
        }, request_id="hist-1")

    monkeypatch.setattr(hithink.httpx, "get", fake_get)
    client = hithink.HiThinkFinanceClient(enabled=True, api_key="secret-key")

    bars, request_id = client.historical("000001", "20260827", "20260828")

    historical_call = next(item for item in calls if item[0].endswith("/api/a-share/prices/historical"))
    params = historical_call[1]["params"]
    assert params["thscode"] == "000001.SZ"
    assert params["interval"] == "1d"
    assert params["adjust"] == "forward"
    assert isinstance(params["start"], int)
    assert isinstance(params["end"], int)
    assert request_id == "hist-1"
    assert bars[0]["close"] == "10.6"
    assert bars[0]["adjustment"] == "qfq"
    assert bars[0]["source"] == hithink.HISTORY_SOURCE_NAME


def test_quote_provider_failure_falls_back_to_existing_chain(monkeypatch):
    class FailedClient:
        available = True

        def quotes(self, _symbols):
            raise hithink.HiThinkFinanceError("denied", code=2003, request_id="req-denied")

    fallback_calls = []
    monkeypatch.setattr(hithink, "_client_for", lambda _service: FailedClient())
    monkeypatch.setattr(
        hithink,
        "_ORIGINAL_MARKET_QUOTES",
        lambda _service, symbols, force_refresh=False: fallback_calls.append((symbols, force_refresh)) or [{
            "symbol": "600519",
            "price": 1499.0,
            "source": "existing provider chain",
        }],
    )

    result = hithink._quotes_with_hithink(SimpleNamespace(), ["600519"], force_refresh=True)

    assert result[0]["source"] == "existing provider chain"
    assert fallback_calls == [(["600519"], True)]
