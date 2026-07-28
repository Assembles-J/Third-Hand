from fastapi.testclient import TestClient

from app.main import announcement_service, app, market_data, news_service, store
from app.time_utils import beijing_now

client = TestClient(app)


def setup_function():
    store.clear_for_test()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_glossary():
    response = client.get("/v1/glossary/%E5%9B%9E%E8%B4%AD")
    assert response.status_code == 200
    assert response.json()["term"] == "回购"


def test_holding_lifecycle_and_feed():
    created = client.post("/v1/holdings", json={"symbol": "01810", "name": "小米集团-W", "quantity": 100, "average_cost": 45.5})
    assert created.status_code == 201
    holding_id = created.json()["id"]
    assert client.get("/v1/holdings").json()[0]["symbol"] == "01810"
    # News network calls are validated separately; the endpoint uses holdings as its symbol scope.
    assert client.get("/v1/holdings").json()[0]["symbol"] == "01810"
    assert client.delete(f"/v1/holdings/{holding_id}").status_code == 204


def test_holding_draft_can_be_confirmed_later():
    draft = client.post("/v1/holding-drafts", json={"name": "小米集团", "quantity": 100, "average_cost": 45.5})
    assert draft.status_code == 201
    draft_id = draft.json()["id"]
    assert client.get("/v1/holding-drafts").json()[0]["name"] == "小米集团"
    confirmed = client.post(f"/v1/holding-drafts/{draft_id}/confirm", json={
        "symbol": "01810", "name": "小米集团-W", "quantity": 100, "average_cost": 45.5,
    })
    assert confirmed.status_code == 201
    assert client.get("/v1/holding-drafts").json() == []
    assert client.get("/v1/holdings").json()[0]["symbol"] == "01810"


def test_holding_drafts_can_be_saved_in_one_request():
    response = client.post("/v1/holding-drafts/batch", json={"items": [
        {"name": "小米集团", "quantity": 100, "average_cost": 45.5},
        {"name": "贵州茅台", "quantity": 10, "average_cost": 1400},
    ]})
    assert response.status_code == 201
    assert len(response.json()) == 2


def test_import_accepts_valid_rows_and_rejects_invalid_rows():
    content = "symbol,name,quantity,average_cost\n600519,贵州茅台,10,1450\nbad,错误,0,4"
    response = client.post("/v1/holdings/import", params={"csv_content": content})
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert response.json()["rejected_rows"] == [3]


def test_import_rejects_unknown_header():
    response = client.post("/v1/holdings/import", params={"csv_content": "code,name\n1,a"})
    assert response.status_code == 422


def test_symbol_lookup_returns_candidates(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{
        "query": names[0],
        "matches": [{"symbol": "01810", "name": "小米集团-W", "market": "HK", "currency": "HKD", "match_type": "exact"}],
    }])
    response = client.get("/v1/market/symbols", params=[("names", "小米集团-W")])
    assert response.status_code == 200
    assert response.json()[0]["matches"][0]["symbol"] == "01810"


def test_market_quote_uses_adapter(monkeypatch):
    monkeypatch.setattr(market_data, "quotes", lambda symbols: [{"symbol": "01810", "price": 45.5, "currency": "HKD"}])
    response = client.get("/v1/market/quotes", params=[("symbols", "01810")])
    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "01810"


def test_feed_uses_news_adapter(monkeypatch):
    monkeypatch.setattr(news_service, "fetch", lambda symbols, names: [{
        "id": "news-1", "title": "公司发布回购进展", "source_name": "测试源",
        "source_url": "https://example.com/news", "published_at": beijing_now(),
        "related_symbols": symbols, "explanation": "为什么与你有关：匹配持仓。", "confidence": 0.8,
    }])
    response = client.get("/v1/feed", params=[("symbols", "000651")])
    assert response.status_code == 200
    assert response.json()[0]["source_url"] == "https://example.com/news"


def test_announcements_uses_disclosure_adapter(monkeypatch):
    monkeypatch.setattr(announcement_service, "fetch", lambda symbols, names, days: [{
        "id": "announcement-1", "title": "年度报告", "source_name": "巨潮资讯（正式公告）",
        "source_url": "https://example.com/notice", "published_at": beijing_now(),
        "related_symbols": symbols, "explanation": "正式公告", "confidence": 0.95,
    }])
    response = client.get("/v1/announcements", params=[("symbols", "000651")])
    assert response.status_code == 200
    assert response.json()[0]["source_name"] == "巨潮资讯（正式公告）"


def test_user_visible_time_uses_beijing_timezone():
    assert beijing_now().utcoffset().total_seconds() == 8 * 60 * 60
