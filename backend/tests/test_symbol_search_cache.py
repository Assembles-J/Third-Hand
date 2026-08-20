import json
import time

from app.application_services.market.symbol_search_service import SymbolSearchService
from app.infrastructure.database.symbol_search_repository import SymbolSearchRepository
from app.storage import PortfolioStore
from app.time_utils import beijing_now


class FakeMarketData:
    def __init__(self, *, delay: float = 0.0, result=None) -> None:
        self.delay = delay
        self.result = result
        self.calls = 0

    def lookup_symbols(self, names):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.result is not None:
            return [self.result]
        query = names[0]
        return [{
            "query": query,
            "matches": [{
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "currency": "CNY",
                "match_type": "exact",
            }],
            "lookup_status": "matched",
            "lookup_message": "找到 1 个候选代码。",
        }]


def make_store(tmp_path):
    return PortfolioStore(tmp_path / "symbol-search.db")


def insert_cached_quote(store, *, symbol="600519", name="贵州茅台"):
    payload = {
        "symbol": symbol,
        "name": name,
        "currency": "HKD" if len(symbol) == 5 else "CNY",
        "price": 1500.0,
    }
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO market_quote_cache(symbol,payload,updated_at) VALUES(?,?,?)",
            (symbol, json.dumps(payload, ensure_ascii=False), beijing_now().isoformat()),
        )


def insert_legacy_symbol_lookup(store):
    payload = [{
        "symbol": "01810",
        "name": "小米集团-W",
        "market": "HK",
        "currency": "HKD",
        "match_type": "exact",
    }]
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO symbol_lookup_cache(name,payload,updated_at) VALUES(?,?,?)",
            ("小米集团-W", json.dumps(payload, ensure_ascii=False), beijing_now().isoformat()),
        )


def test_existing_database_symbol_is_returned_without_remote_call(tmp_path):
    store = make_store(tmp_path)
    insert_cached_quote(store)
    repository = SymbolSearchRepository(store)
    remote = FakeMarketData(delay=0.2)
    service = SymbolSearchService(repository, remote)

    result = service.search("600519")

    assert result["lookup_status"] == "matched"
    assert result["matches"][0]["symbol"] == "600519"
    assert result["matches"][0]["match_type"] == "database"
    assert remote.calls == 0


def test_xiaomi_typing_sequence_stays_local_and_never_calls_remote(tmp_path):
    store = make_store(tmp_path)
    insert_legacy_symbol_lookup(store)
    repository = SymbolSearchRepository(store)
    remote = FakeMarketData(delay=0.2)
    service = SymbolSearchService(repository, remote)

    for query in ("小米", "小米集团", "小米集团-W", "01810"):
        result = service.search(query)
        assert result["lookup_status"] == "matched"
        assert result["matches"][0]["symbol"] == "01810"

    assert remote.calls == 0


def test_local_directory_supports_code_prefix_without_remote_completion(tmp_path):
    store = make_store(tmp_path)
    insert_cached_quote(store)
    repository = SymbolSearchRepository(store)
    remote = FakeMarketData(delay=0.2)
    service = SymbolSearchService(repository, remote)

    result = service.search("6005")

    assert [item["symbol"] for item in result["matches"]] == ["600519"]
    assert result["lookup_status"] == "matched"
    assert remote.calls == 0


def test_remote_lookup_returns_pending_immediately_then_warms_cache(tmp_path):
    store = make_store(tmp_path)
    repository = SymbolSearchRepository(store)
    remote = FakeMarketData(delay=0.6)
    service = SymbolSearchService(repository, remote)

    started = time.monotonic()
    first = service.search("贵州茅台")
    elapsed = time.monotonic() - started

    assert elapsed < 0.3
    assert first["lookup_status"] == "pending"
    assert first["matches"] == []

    deadline = time.monotonic() + 3
    latest = first
    while time.monotonic() < deadline:
        latest = service.search("贵州茅台")
        if latest["lookup_status"] == "matched":
            break
        time.sleep(0.05)

    assert latest["lookup_status"] == "matched"
    assert latest["matches"][0]["symbol"] == "600519"
    assert remote.calls == 1
    assert repository.cached_lookup("贵州茅台") is not None


def test_repeated_polling_does_not_duplicate_inflight_remote_request(tmp_path):
    store = make_store(tmp_path)
    repository = SymbolSearchRepository(store)
    remote = FakeMarketData(delay=0.25)
    service = SymbolSearchService(repository, remote)

    first = service.search("贵州茅台")
    second = service.search("贵州茅台")

    assert first["lookup_status"] == "pending"
    assert second["lookup_status"] == "pending"

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        result = service.search("贵州茅台")
        if result["lookup_status"] == "matched":
            break
        time.sleep(0.05)

    assert remote.calls == 1


def test_negative_remote_result_is_cached_and_not_refetched(tmp_path):
    store = make_store(tmp_path)
    repository = SymbolSearchRepository(store)
    remote = FakeMarketData(
        delay=0.05,
        result={
            "query": "不存在",
            "matches": [],
            "lookup_status": "not_found",
            "lookup_message": "未找到匹配的证券代码。",
        },
    )
    service = SymbolSearchService(repository, remote)

    service.search("不存在")
    deadline = time.monotonic() + 2
    latest = None
    while time.monotonic() < deadline:
        latest = service.search("不存在")
        if latest["lookup_status"] == "not_found":
            break
        time.sleep(0.05)

    again = service.search("不存在")

    assert latest is not None
    assert latest["lookup_status"] == "not_found"
    assert again["lookup_status"] == "not_found"
    assert remote.calls == 1


def test_partial_remote_failure_is_not_saved_as_negative_cache(tmp_path):
    store = make_store(tmp_path)
    repository = SymbolSearchRepository(store)
    remote = FakeMarketData(
        delay=0.05,
        result={
            "query": "贵州茅台",
            "matches": [],
            "lookup_status": "partial_failure",
            "lookup_message": "部分代码表暂不可用，未找到匹配项。",
        },
    )
    service = SymbolSearchService(repository, remote)

    first = service.search("贵州茅台")
    assert first["lookup_status"] == "pending"

    deadline = time.monotonic() + 2
    latest = first
    while time.monotonic() < deadline:
        latest = service.search("贵州茅台")
        if latest["lookup_status"] == "remote_error":
            break
        time.sleep(0.05)

    assert latest["lookup_status"] == "remote_error"
    assert repository.cached_lookup("贵州茅台") is None
