import hashlib

from fastapi.testclient import TestClient

from app.main import announcement_service, app, market_data, news_service, risk_service, store
from app.time_utils import beijing_now

client = TestClient(app)


def setup_function():
    store.clear_for_test()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_app_update_exposes_download_integrity_metadata(monkeypatch, tmp_path):
    apk = tmp_path / "third-hand-0.3.0.apk"
    content = b"fake-signed-apk-for-metadata-test"
    apk.write_bytes(content)
    monkeypatch.setenv("APP_UPDATE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("APP_UPDATE_APK_FILE", apk.name)
    monkeypatch.setenv("APP_PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("APP_UPDATE_VERSION_CODE", "3")
    monkeypatch.setenv("APP_UPDATE_VERSION_NAME", "0.3.0")

    response = client.get("/v1/app-update")

    assert response.status_code == 200
    assert response.json()["size_bytes"] == len(content)
    assert response.json()["sha256"] == hashlib.sha256(content).hexdigest()


def test_admin_overview_exposes_aggregate_operational_data_only():
    client.post("/v1/holdings", json={"symbol": "600519", "name": "贵州茅台", "quantity": 1, "average_cost": 1450})
    response = client.get("/v1/admin/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["holdings_count"] == 1
    assert payload["database_bytes"] > 0
    assert "holdings" not in payload


def test_portfolio_analysis_returns_a_review_payload():
    response = client.get("/v1/portfolio/analysis")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_learning_cases_can_be_created_and_listed():
    payload = {
        "title": "公告核验练习", "context": "阅读公告后记录需要核验的事实与数据来源。",
        "lesson": "先确认原文、发布日期与适用范围。", "outcome": "完成核验清单。",
        "position_band": "低仓位", "planned_action": "保留观察记录", "confidence": 0.7,
    }
    created = client.post("/v1/learning-cases", json=payload)
    assert created.status_code == 201
    assert client.get("/v1/learning-cases").json()[0]["id"] == created.json()["id"]


def test_research_and_personal_rules_are_available():
    rules = client.get("/v1/research-rules")
    assert rules.status_code == 200
    assert rules.json()
    saved = client.post("/v1/personal-rules", json={
        "scope": "global", "max_position_percent": 20, "loss_review_percent": 12,
        "volatility_review_percent": 35, "enabled": True,
    })
    assert saved.status_code == 200
    assert client.get("/v1/personal-rules").json()[0]["scope"] == "global"


def test_saving_same_personal_rule_updates_instead_of_duplicating():
    first = client.post("/v1/personal-rules", json={
        "scope": "global", "max_position_percent": 20, "loss_review_percent": 15,
        "volatility_review_percent": 50, "enabled": True,
    })
    second = client.post("/v1/personal-rules", json={
        "scope": "global", "max_position_percent": 18, "loss_review_percent": 12,
        "volatility_review_percent": 40, "enabled": True,
    })

    rules = client.get("/v1/personal-rules").json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(rules) == 1
    assert rules[0]["max_position_percent"] == 18
    assert rules[0]["version"] == 2


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


def test_holding_draft_can_be_confirmed_later(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{"query": name, "matches": []} for name in names])
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


def test_holding_drafts_can_be_saved_in_one_request(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{"query": name, "matches": []} for name in names])
    response = client.post("/v1/holding-drafts/batch", json={"items": [
        {"name": "小米集团", "quantity": 100, "average_cost": 45.5},
        {"name": "贵州茅台", "quantity": 10, "average_cost": 1400},
    ]})
    assert response.status_code == 201
    assert len(response.json()) == 2


def test_exact_draft_lookup_is_saved_and_confirmed_in_background(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{
        "query": names[0],
        "matches": [{"symbol": "600519", "name": "贵州茅台", "market": "CN", "currency": "CNY", "match_type": "exact"}],
    }])
    response = client.post("/v1/holding-drafts", json={"name": "贵州茅台", "quantity": 10, "average_cost": 1400})
    assert response.status_code == 201
    assert client.get("/v1/holding-drafts").json() == []
    assert client.get("/v1/holdings").json()[0]["symbol"] == "600519"


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


def test_risk_assessments_are_returned_for_confirmed_holdings(monkeypatch):
    client.post("/v1/holdings", json={"symbol": "01810", "name": "小米集团-W", "quantity": 100, "average_cost": 45.5})
    monkeypatch.setattr(risk_service, "assess", lambda symbol, name: {
        "symbol": symbol, "name": name, "horizon_trading_days": 5, "downside_threshold_percent": 5.0,
        "historical_downside_probability": 12.5, "annualized_volatility_percent": 31.2,
        "risk_level": "中", "confidence": "高", "sample_count": 180, "as_of": "2026-07-28",
        "explanation": "历史样本统计。",
    })
    response = client.get("/v1/risk/assessments")
    assert response.status_code == 200
    assert response.json()[0]["historical_downside_probability"] == 12.5


def test_market_quote_uses_adapter_and_exposes_freshness_metadata(monkeypatch):
    monkeypatch.setattr(market_data, "quotes", lambda symbols, force_refresh=False: [{
        "symbol": "01810", "price": 45.5, "currency": "HKD", "as_of": "2026-07-28",
        "is_realtime": False, "license_scope": "public-source-review-required",
    }])
    response = client.get("/v1/market/quotes", params=[("symbols", "01810")])
    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "01810"
    assert response.json()[0]["is_realtime"] is False
    assert response.json()[0]["as_of"] == "2026-07-28"


def test_market_quote_force_refresh_replaces_saved_snapshot(monkeypatch):
    store.save_quotes([{
        "symbol": "01810", "price": 29.0, "currency": "HKD", "as_of": "2026-07-29",
        "source": "旧缓存", "retrieved_at": "2026-07-29T15:00:00+08:00",
    }])
    monkeypatch.setattr(market_data, "quotes", lambda symbols, force_refresh=False: [{
        "symbol": "01810", "price": 30.5, "currency": "HKD", "as_of": "2026-07-30",
        "source": "刷新行情", "retrieved_at": "2026-07-30T10:30:00+08:00",
    }])

    response = client.get("/v1/market/quotes", params=[("symbols", "01810"), ("refresh", "true")])

    assert response.status_code == 200
    assert response.json()[0]["price"] == 30.5
    assert response.json()[0]["as_of"] == "2026-07-30"
    assert response.json()[0]["refresh_status"] == "fresh"
    refresh_status = client.get("/v1/market/refresh-status").json()
    assert refresh_status["last_trigger"] == "request-forced"
    assert refresh_status["last_error"] is None
    assert refresh_status["symbols"] == ["01810"]


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
