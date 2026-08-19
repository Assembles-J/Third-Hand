from datetime import datetime
from types import SimpleNamespace
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import httpx

from app.hkex_corporate_event_runtime import install as install_hkex_runtime
from app.hkex_corporate_events import (
    HKEX_ACTIVE_STOCKS_URL,
    HKEX_EVENT_ADAPTER_VERSION,
    HKEX_TITLE_SEARCH_URL,
    HkexOfficialEventFetcher,
    _parse_title_search_rows,
)


HK_TZ = ZoneInfo("Asia/Hong_Kong")


def _result_row(title="INTERIM RESULTS ANNOUNCEMENT"):
    return f"""
    <table>
      <tr>
        <td class="release-time"><span>Release Time:</span>18/08/2026 19:05</td>
        <td class="stock-short-code"><span>Stock Code:</span>01810</td>
        <td><div class="headline">Announcements and Notices - [Interim Results]</div></td>
        <td><div class="doc-link"><a href="/listedco/listconews/sehk/2026/0818/2026081809999.pdf">{title}</a></div></td>
      </tr>
    </table>
    """


def test_parser_promotes_only_published_result_announcements_to_official_lifecycle():
    page = _result_row() + """
    <table><tr>
      <td class="release-time"><span>Release Time:</span>17/07/2026 19:00</td>
      <td class="stock-short-code"><span>Stock Code:</span>01810</td>
      <td><div class="headline">Announcements and Notices - [Date of Board Meeting]</div></td>
      <td><div class="doc-link"><a href="/board.pdf">DATE OF BOARD MEETING</a></div></td>
    </tr></table>
    """

    rows = _parse_title_search_rows(page, "01810")

    assert len(rows) == 1
    item = rows[0]
    assert item["symbol"] == "01810"
    assert item["market"] == "HK"
    assert item["period"] == "2026年中报"
    assert item["scheduled_date"] == "2026-08-18"
    assert item["verification_level"] == "official"
    assert item["source_rank"] == 10
    assert item["lifecycle_status"] == "RELEASED_UNVERIFIED"
    assert item["announced_at"] == "2026-08-18T19:05:00"
    assert item["parser_version"] == HKEX_EVENT_ADAPTER_VERSION
    assert item["source_reference"].startswith("https://www.hkexnews.hk/")


def test_fetcher_resolves_hkex_stock_id_and_posts_bounded_title_search():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if str(request.url) == HKEX_ACTIVE_STOCKS_URL:
            assert request.method == "GET"
            return httpx.Response(200, json=[{"c": "01810", "i": "190371", "n": "XIAOMI-W"}])
        assert request.method == "POST"
        assert str(request.url) == HKEX_TITLE_SEARCH_URL
        form = parse_qs(request.content.decode())
        assert form["stockId"] == ["190371"]
        assert form["market"] == ["SEHK"]
        assert form["category"] == ["0"]
        assert form["sortByOptions"] == ["DateTime"]
        assert form["from"] == ["20260420"]
        assert form["to"] == ["20260818"]
        return httpx.Response(200, text=_result_row())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = HkexOfficialEventFetcher(client=client, lookback_days=120)
    now = datetime(2026, 8, 18, 20, 0, tzinfo=HK_TZ)

    first = fetcher(symbol="01810", market="HK", now=now)
    second = fetcher(symbol="01810", market="HK", now=now)

    assert len(first) == 1
    assert first == second
    # Stock-id lookup is memory cached. Title search remains refreshable; the
    # outer CorporateEventService owns the daily persisted fetch cache.
    assert [request.method for request in requests] == ["GET", "POST", "POST"]


def test_fetcher_is_market_scoped_and_does_not_contact_hkex_for_cn():
    def handler(_request):
        raise AssertionError("non-HK symbol must not contact HKEX")

    fetcher = HkexOfficialEventFetcher(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert fetcher(
        symbol="600000",
        market="CN",
        now=datetime(2026, 8, 18, 15, 0, tzinfo=HK_TZ),
    ) == []


def test_runtime_wires_official_fetcher_only_after_corporate_event_service_exists():
    service = SimpleNamespace(_official_fetcher=None)
    module = SimpleNamespace(corporate_event_service=service)

    install_hkex_runtime(module)

    assert isinstance(service._official_fetcher, HkexOfficialEventFetcher)
    first = service._official_fetcher
    install_hkex_runtime(module)
    assert service._official_fetcher is first


def test_runtime_without_corporate_event_service_is_safe_noop():
    module = SimpleNamespace()
    install_hkex_runtime(module)
    assert module._hkex_corporate_event_runtime_installed is True
