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
    monkeypatch.setenv("APP_UPDATE_PUBLIC_BASE_URL", "https://download.example.com/third-hand/releases")
    monkeypatch.setenv("APP_UPDATE_VERSION_CODE", "3")
    monkeypatch.setenv("APP_UPDATE_VERSION_NAME", "0.3.0")

    response = client.get("/v1/app-update")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["apk_url"] == "https://download.example.com/third-hand/releases/third-hand-0.3.0.apk"
    assert response.json()["size_bytes"] == len(content)
    assert response.json()["sha256"] == hashlib.sha256(content).hexdigest()


def test_app_update_falls_back_to_api_download(monkeypatch, tmp_path):
    apk = tmp_path / "third-hand-0.3.1.apk"
    apk.write_bytes(b"apk")
    monkeypatch.setenv("APP_UPDATE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("APP_UPDATE_APK_FILE", apk.name)
    monkeypatch.setenv("APP_PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.delenv("APP_UPDATE_PUBLIC_BASE_URL", raising=False)

    response = client.get("/v1/app-update")

    assert response.status_code == 200
    assert response.json()["apk_url"] == "https://api.example.com/v1/app-update/apk"


def test_versioned_api_apk_download_is_immutable(monkeypatch, tmp_path):
    apk = tmp_path / "third-hand-0.3.2.apk"
    apk.write_bytes(b"apk")
    monkeypatch.setenv("APP_UPDATE_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("APP_UPDATE_APK_FILE", apk.name)

    response = client.get("/v1/app-update/apk")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


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


def test_decision_context_debug_endpoint_persists_a_read_only_snapshot():
    client.post("/v1/holdings", json={"symbol": "600519", "name": "test", "quantity": 100, "average_cost": 10})
    client.put("/v1/account/cash", json={"available_cash": 1000})
    store.save_quotes([{"symbol": "600519", "price": 12, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", [{"trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 12, "high": 13, "low": 9, "source": "test"} for index in range(60)])
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1})

    response = client.get("/v1/decisions/context/600519")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519"
    assert payload["position"]["market_value"] == 1200
    assert payload["data_quality"]["status"] == "degraded"
    assert "action" not in payload
    assert store.decision_context(payload["context_id"])["input_hash"] == payload["input_hash"]


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


def test_glossary_lookup_saves_custom_explanation_for_later_queries():
    missing = client.post("/v1/glossary/lookup", json={"term": "量价背离", "context": "MACD 出现量价背离"})
    assert missing.status_code == 200
    assert missing.json()["found"] is False

    saved = client.post("/v1/glossary", json={
        "term": "量价背离", "plain_explanation": "价格和成交量的变化方向不一致，需要回看具体区间。",
        "watch_for": "不要只用一个指标下结论。",
    })
    assert saved.status_code == 200
    assert saved.json()["source"] == "user"

    found = client.post("/v1/glossary/lookup", json={"term": "量价背离"})
    assert found.status_code == 200
    assert found.json()["found"] is True
    assert found.json()["plain_explanation"].startswith("价格和成交量")


def test_holding_lifecycle_and_feed():
    created = client.post("/v1/holdings", json={"symbol": "01810", "name": "小米集团-W", "quantity": 100, "average_cost": 45.5})
    assert created.status_code == 201
    holding_id = created.json()["id"]
    assert client.get("/v1/holdings").json()[0]["symbol"] == "01810"
    # News network calls are validated separately; the endpoint uses holdings as its symbol scope.
    assert client.get("/v1/holdings").json()[0]["symbol"] == "01810"
    assert client.delete(f"/v1/holdings/{holding_id}").status_code == 204


def test_sale_records_realized_profit_and_reduces_holding():
    holding = client.post("/v1/holdings", json={"symbol": "600519", "name": "贵州茅台", "quantity": 10, "average_cost": 1000}).json()
    response = client.post(f"/v1/holdings/{holding['id']}/sales", json={"quantity": 4, "sale_price": 1200, "reason": "达到预先设定的仓位上限"})
    assert response.status_code == 201
    sale = response.json()
    assert sale["realized_pnl"] == 800
    assert sale["remaining_quantity"] == 6
    assert sale["reason"]
    assert client.get("/v1/holdings").json()[0]["quantity"] == 6
    assert client.get("/v1/sales").json()[0]["id"] == sale["id"]


def test_sale_rejects_quantity_above_position():
    holding = client.post("/v1/holdings", json={"symbol": "600519", "name": "贵州茅台", "quantity": 2, "average_cost": 1000}).json()
    response = client.post(f"/v1/holdings/{holding['id']}/sales", json={"quantity": 3, "sale_price": 1200})
    assert response.status_code == 422
    assert client.get("/v1/holdings").json()[0]["quantity"] == 2


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
    assert response.json()[0]["client_row_id"] == response.json()[0]["id"]


def test_exact_draft_lookup_stays_in_preview_until_user_confirms(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{
        "query": names[0],
        "matches": [{"symbol": "600519", "name": "贵州茅台", "market": "CN", "currency": "CNY", "match_type": "exact"}],
    }])
    response = client.post("/v1/holding-drafts", json={
        "client_row_id": "ocr-row-7", "name": "贵州茅台", "quantity": 10, "average_cost": 1400,
    })
    assert response.status_code == 201
    drafts = client.get("/v1/holding-drafts").json()
    assert drafts[0]["client_row_id"] == "ocr-row-7"
    assert drafts[0]["lookup_status"] == "matched"
    assert drafts[0]["candidates"][0]["symbol"] == "600519"
    assert client.get("/v1/holdings").json() == []


def test_batch_commit_uses_quantity_and_cost_from_bound_draft_rows(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{"query": name, "matches": []} for name in names])
    created = client.post("/v1/holding-drafts/batch", json={"items": [
        {"client_row_id": "row-a", "name": "小米集团", "quantity": 200, "average_cost": 26.96},
        {"client_row_id": "row-b", "name": "贵州茅台", "quantity": 10, "average_cost": 1400},
    ]}).json()

    response = client.post("/v1/holding-drafts/commit", json={"items": [
        {"draft_id": created[0]["id"], "symbol": "01810", "name": "小米集团-W"},
        {"draft_id": created[1]["id"], "symbol": "600519", "name": "贵州茅台"},
    ]})

    assert response.status_code == 201
    holdings = {item["symbol"]: item for item in response.json()}
    assert holdings["01810"]["quantity"] == 200
    assert holdings["01810"]["average_cost"] == 26.96
    assert client.get("/v1/holding-drafts").json() == []


def test_batch_commit_is_atomic_when_any_draft_is_missing(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{"query": name, "matches": []} for name in names])
    draft = client.post("/v1/holding-drafts", json={
        "client_row_id": "row-a", "name": "小米集团", "quantity": 200, "average_cost": 26.96,
    }).json()

    response = client.post("/v1/holding-drafts/commit", json={"items": [
        {"draft_id": draft["id"], "symbol": "01810", "name": "小米集团-W"},
        {"draft_id": "missing", "symbol": "600519", "name": "贵州茅台"},
    ]})

    assert response.status_code == 409
    assert client.get("/v1/holdings").json() == []
    assert client.get("/v1/holding-drafts").json()[0]["id"] == draft["id"]


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


def test_symbol_lookup_post_resolves_names_without_query_params(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{
        "query": names[0],
        "matches": [{"symbol": "600519", "name": "贵州茅台", "market": "CN", "currency": "CNY", "match_type": "exact"}],
        "lookup_status": "matched",
        "lookup_message": "找到 1 个候选代码。",
    }])

    response = client.post("/v1/market/symbols/resolve", json={"names": ["贵州茅台"]})

    assert response.status_code == 200
    assert response.json()[0]["matches"][0]["symbol"] == "600519"
    assert response.json()[0]["lookup_status"] == "matched"


def test_risk_assessments_are_returned_for_confirmed_holdings(monkeypatch):
    client.post("/v1/holdings", json={"symbol": "01810", "name": "小米集团-W", "quantity": 100, "average_cost": 45.5})
    store.save_risk({
        "symbol": "01810", "name": "小米集团-W", "horizon_trading_days": 5, "downside_threshold_percent": 5.0,
        "historical_downside_probability": 12.5, "annualized_volatility_percent": 31.2,
        "risk_level": "中", "confidence": "高", "sample_count": 180, "as_of": "2026-07-28",
        "explanation": "历史样本统计。",
    })
    response = client.get("/v1/risk/assessments")
    assert response.status_code == 200
    assert response.json()[0]["historical_downside_probability"] == 12.5


def test_market_quote_reads_persisted_snapshot_without_calling_adapter(monkeypatch):
    store.save_quotes([{
        "symbol": "01810", "price": 45.5, "currency": "HKD", "as_of": "2026-07-28",
        "is_realtime": False, "license_scope": "public-source-review-required",
    }])
    monkeypatch.setattr(market_data, "quotes", lambda *_: (_ for _ in ()).throw(AssertionError("HTTP must not query provider")))
    response = client.get("/v1/market/quotes", params=[("symbols", "01810")])
    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "01810"
    assert response.json()[0]["is_realtime"] is False
    assert response.json()[0]["as_of"] == "2026-07-28"
    assert response.json()[0]["refresh_status"] == "stored"


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
    assert response.json()[0]["price"] == 29.0
    assert response.json()[0]["as_of"] == "2026-07-29"
    assert response.json()[0]["refresh_status"] == "stored"


def test_market_quote_post_keeps_valid_result_when_another_symbol_fails(monkeypatch):
    monkeypatch.setattr(market_data, "quotes", lambda symbols, force_refresh=False: [
        {
            "symbol": "600519", "name": "贵州茅台", "price": 1500.0, "currency": "CNY",
            "source": "刷新行情", "retrieved_at": "2026-07-30T10:30:00+08:00",
        },
        {
            "symbol": "BAD", "name": "BAD", "price": None, "currency": "CNY",
            "source": "行情错误", "retrieved_at": "2026-07-30T10:30:00+08:00",
            "error_code": "invalid_symbol", "error_message": "代码格式错误",
        },
    ])

    response = client.post("/v1/market/quotes/batch", json={"symbols": ["600519", "BAD"], "refresh": True})

    assert response.status_code == 200
    assert [item["symbol"] for item in response.json()] == ["600519", "BAD"]
    assert response.json()[0]["price"] is None
    assert response.json()[0]["refresh_status"] == "pending"
    assert response.json()[1]["refresh_status"] == "pending"


def test_market_quote_failure_falls_back_to_cache_for_only_that_symbol(monkeypatch):
    store.save_quotes([{
        "symbol": "01810", "name": "小米集团-W", "price": 29.0, "currency": "HKD",
        "source": "旧缓存", "retrieved_at": "2026-07-29T15:00:00+08:00",
    }])
    monkeypatch.setattr(market_data, "quotes", lambda symbols, force_refresh=False: [
        {
            "symbol": "01810", "name": "01810", "price": None, "currency": "HKD",
            "source": "行情错误", "retrieved_at": "2026-07-30T10:30:00+08:00",
            "error_code": "upstream_unavailable", "error_message": "港股行情暂不可用",
        },
        {
            "symbol": "600519", "name": "贵州茅台", "price": 1500.0, "currency": "CNY",
            "source": "刷新行情", "retrieved_at": "2026-07-30T10:30:00+08:00",
        },
    ])

    response = client.post("/v1/market/quotes/batch", json={"symbols": ["01810", "600519"], "refresh": True})

    assert response.status_code == 200
    assert response.json()[0]["price"] == 29.0
    assert response.json()[0]["refresh_status"] == "stored"
    assert response.json()[1]["price"] is None
    assert response.json()[1]["refresh_status"] == "pending"


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
