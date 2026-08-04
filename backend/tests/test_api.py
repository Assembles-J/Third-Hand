import hashlib
import json
import time

from fastapi.testclient import TestClient

import app.main as main
from app.main import announcement_service, app, market_data, news_service, risk_service, store
from app.time_utils import beijing_now

client = TestClient(app)


def setup_function():
    store.clear_for_test()
    main.daily_history_refreshed_for.clear()
    main.daily_history_attempted_for.clear()
    main.daily_history_retry_after.clear()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_derived_refresh_skips_empty_daily_history_without_aborting(monkeypatch):
    class MarketRegimeFixture:
        def assess(self):
            return {"status": "unavailable"}

    store.add("holding-1", "600519", "test", 100, 10)
    main.daily_history_attempted_for["600519"] = beijing_now().date().isoformat()
    main.daily_history_retry_after["600519"] = time.monotonic() + 60
    monkeypatch.setattr(main, "market_regime_service", MarketRegimeFixture())

    main.refresh_derived_cache(["600519"], "test-empty-history")

    assert store.daily_prices("600519") == []
    assert store.cached_portfolio_analysis() is not None


def test_manual_daily_history_refresh_returns_fresh_bars(monkeypatch):
    def refresh_history(target_store, symbol):
        target_store.replace_daily_prices(symbol, [{
            "trading_date": "2026-08-03", "open": 10, "close": 11,
            "high": 12, "low": 9, "source": "test",
        }, {
            "trading_date": "2026-08-04", "open": 11, "close": 12,
            "high": 13, "low": 10, "source": "test",
        }])
        return 2

    monkeypatch.setattr(main.price_history_service, "refresh", refresh_history)
    monkeypatch.setattr(main, "queue_background", lambda *_: None)

    response = client.post("/v1/market/history/600519/refresh")

    assert response.status_code == 200
    assert [item["trading_date"] for item in response.json()] == ["2026-08-03", "2026-08-04"]


def test_delete_market_history_purges_one_symbol_cache():
    store.save_daily_prices("01810", [{
        "trading_date": "999", "open": 12, "close": 12, "high": 12, "low": 12, "source": "legacy",
    }])

    response = client.delete("/v1/market/history/01810")

    assert response.status_code == 204
    assert store.daily_prices("01810") == []


def test_ai_capabilities_are_sanitized(monkeypatch):
    monkeypatch.setenv("DECISION_AI_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_CHAT_ENABLED", "true")
    response = client.get("/v1/system/ai-capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_ai_enabled"] is True
    assert payload["research_chat_enabled"] is True
    assert "api_key" not in payload
    assert "DEEPSEEK_API_KEY" not in response.text


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


def test_daily_review_generation_returns_a_pending_review_when_data_is_incomplete():
    store.add("holding-1", "600519", "贵州茅台", 100, 10)

    response = client.post("/v1/daily-reviews/generate", json={})

    assert response.status_code == 201
    payload = response.json()
    assert payload["items"][0]["action"] == "watch"
    assert "缺少实时行情" in payload["items"][0]["rationale"]
    assert "共用决策规则" in payload["items"][0]["rationale"]


def test_daily_review_generation_without_holdings_is_an_empty_pending_review():
    response = client.post("/v1/daily-reviews/generate")

    assert response.status_code == 201
    assert response.json()["items"] == []


def test_research_session_daily_history_refresh_is_confirmed_and_persisted(monkeypatch):
    monkeypatch.setenv("RESEARCH_CHAT_ENABLED", "true")
    session = client.post("/v1/research-chat/sessions", json={"title": "日线补齐", "primary_symbol": "600519"}).json()

    status = client.get(f"/v1/research-chat/sessions/{session['id']}/daily-history-refresh")
    assert status.status_code == 200
    assert status.json()["status"] == "not_requested"

    monkeypatch.setattr(main.price_history_service, "refresh", lambda _store, _symbol: 0)
    requested = client.post(f"/v1/research-chat/sessions/{session['id']}/daily-history-refresh")
    assert requested.status_code == 202
    assert requested.json()["status"] == "queued"


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


def test_decision_evidence_endpoint_returns_evidence_but_no_action():
    client.post("/v1/holdings", json={"symbol": "600519", "name": "test", "quantity": 100, "average_cost": 10})
    store.save_quotes([{"symbol": "600519", "price": 12, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", [{"trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 12, "high": 13, "low": 9, "source": "test"} for index in range(60)])
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1})

    response = client.get("/v1/decisions/evidence/600519")

    assert response.status_code == 200
    assert any(item["evidence_id"] == "data_quality.summary" for item in response.json())
    assert all("action" not in item for item in response.json())


def test_decision_shadow_endpoint_persists_policy_candidates_without_replacing_recommendations():
    client.post("/v1/holdings", json={"symbol": "600519", "name": "test", "quantity": 100, "average_cost": 10})
    store.save_quotes([{ "symbol": "600519", "price": 12, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", [{"trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 12, "high": 13, "low": 9, "source": "test"} for index in range(60)])
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1})

    response = client.get("/v1/decisions/shadow/600519")

    assert response.status_code == 200
    assert response.json()["shadow_mode"] is True
    assert response.json()["action_candidates"]
    assert response.json()["sizing"] is None
    assert response.json()["policy_version"] == "swing-policy-v1"
    assert store.shadow_reports("600519")[0]["shadow_id"] == response.json()["shadow_id"]
    assert client.get("/v1/research-recommendations").json() == []


def test_recommendation_evaluation_uses_only_future_bars_and_marks_legacy_or_untriggered_records():
    bars = [
        {"trading_date": "2026-07-30", "open": 10, "high": 11, "low": 9, "close": 10, "source": "test"},
        {"trading_date": "2026-07-31", "open": 10, "high": 11, "low": 9, "close": 10, "source": "test"},
    ]
    store.save_daily_prices("600519", bars)
    store.save_recommendation({"id": "current", "symbol": "600519", "status": "ready", "action": "add", "suggested_quantity": 100, "price_zone": {"low": 9, "high": 11}, "generated_trading_date": "2026-07-30", "evaluation_status": "pending"})
    store.save_recommendation({"id": "legacy", "symbol": "600519", "status": "ready", "action": "add", "suggested_quantity": 100, "price_zone": {"low": 9, "high": 11}})
    store.save_recommendation({"id": "untriggered", "symbol": "600519", "status": "ready", "action": "add", "suggested_quantity": 100, "price_zone": {"low": 1, "high": 2}, "generated_trading_date": "2026-07-30", "evaluation_status": "pending"})

    response = client.post("/v1/research-recommendations/evaluate")
    statuses = {item["id"]: item.get("evaluation_status") for item in store.recommendations()}

    assert response.json() == {"evaluated": 1, "untriggered": 1, "legacy_unverifiable": 1}
    assert statuses == {"current": "filled", "legacy": "legacy_unverifiable", "untriggered": "untriggered"}


def test_daily_review_closes_the_plan_execution_outcome_loop():
    client.post("/v1/holdings", json={"symbol": "600519", "name": "test", "quantity": 100, "average_cost": 10})
    store.save_available_cash(10000)
    store.save_quotes([{ "symbol": "600519", "price": 10, "currency": "CNY", "source": "test", "as_of": "2026-07-30", "retrieved_at": "2026-07-30T15:00:00+08:00" }])
    bars = [{"trading_date": f"2026-05-{day:02d}", "open": 10, "high": 11, "low": 9, "close": 10, "source": "test"} for day in range(1, 31)]
    bars += [{"trading_date": f"2026-07-{day:02d}", "open": 10, "high": 11, "low": 9, "close": 10, "source": "test"} for day in range(1, 31)]
    store.save_daily_prices("600519", bars)
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1})

    generated = client.post("/v1/daily-reviews/generate", json={"symbols": ["600519"]})
    assert generated.status_code == 201
    review = generated.json()
    item = review["items"][0]
    store.save_daily_prices("600519", bars + [{"trading_date": "2026-07-31", "open": 10, "high": 12, "low": 10, "close": 11, "source": "test"}])
    # Missing risk inputs make the shared workbench policy choose WATCH; this
    # must not manufacture a paper trade merely to make the daily page active.
    assert item["action"] == "watch"
    recorded = client.put(f"/v1/daily-reviews/{review['id']}/items/600519/execution", json={"execution_status": "skipped", "executed_quantity": 0})
    assert recorded.status_code == 200
    result = client.post(f"/v1/daily-reviews/{review['id']}/evaluate")
    assert result.status_code == 200
    assert result.json()["status"] == "evaluated"
    assert result.json()["items"][0]["theoretical_pnl"] is not None


def test_decision_generation_is_async_idempotent_and_persists_a_report():
    client.post("/v1/holdings", json={"symbol": "600519", "name": "test", "quantity": 100, "average_cost": 10})
    store.save_quotes([{ "symbol": "600519", "price": 12, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", [{"trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 12, "high": 13, "low": 9, "source": "test"} for index in range(60)])
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1})

    first = client.post("/v1/decisions/generate", json={"symbols": ["600519"]}).json()["jobs"][0]
    second = client.post("/v1/decisions/generate", json={"symbols": ["600519"]}).json()["jobs"][0]
    for _ in range(20):
        job = client.get(f"/v1/decisions/jobs/{first['job_id']}").json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(.02)

    assert first["job_id"] == second["job_id"]
    assert job["status"] == "succeeded"
    assert client.get("/v1/decisions/latest", params={"symbol": "600519"}).json()["automatic_execution"] is False


def test_decision_history_deletes_incomplete_legacy_reports():
    broken = {
        "decision_id": "legacy-broken-report",
        "context_id": "legacy-context",
        "symbol": "600519",
        "input_hash": "legacy-input",
        "generated_at": "2026-08-04T00:00:00+08:00",
        "evidence": [],
        "action_candidates": [],
        "operation_items": [],
        "ai_assessment": {
            "supporting_evidence_ids": [],
            "opposing_evidence_ids": [],
            "missing_evidence": [],
            "reasoning_steps": [],
            "rule_suggestions": None,
        },
    }
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO decision_reports VALUES (?,?,?,?,?,?)",
            ("legacy-broken-report", "legacy-context", "600519", "legacy-input", json.dumps(broken), broken["generated_at"]),
        )

    response = client.get("/v1/decisions", params={"symbol": "600519"})

    assert response.status_code == 200
    assert response.json() == []
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM decision_reports WHERE decision_id='legacy-broken-report'").fetchone()[0] == 0


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
    client.put("/v1/account/cash", json={"available_cash": 1000})
    holding = client.post("/v1/holdings", json={"symbol": "600519", "name": "贵州茅台", "quantity": 10, "average_cost": 1000}).json()
    response = client.post(f"/v1/holdings/{holding['id']}/sales", json={"quantity": 4, "sale_price": 1200, "reason": "达到预先设定的仓位上限"})
    assert response.status_code == 201
    sale = response.json()
    assert sale["realized_pnl"] == 800
    assert sale["remaining_quantity"] == 6
    assert sale["reason"]
    assert client.get("/v1/holdings").json()[0]["quantity"] == 6
    assert client.get("/v1/sales").json()[0]["id"] == sale["id"]
    assert client.get("/v1/account/cash").json()["available_cash"] == 5800


def test_full_sale_keeps_symbol_available_as_a_research_target_and_reentry_reuses_it():
    holding = client.post("/v1/holdings", json={"symbol": "01810", "name": "小米集团", "quantity": 10, "average_cost": 40}).json()
    store.save_daily_prices("01810", [{"trading_date": "2026-08-01", "open": 40, "close": 42, "high": 43, "low": 39, "source": "test"}])

    sale = client.post(f"/v1/holdings/{holding['id']}/sales", json={"quantity": 10, "sale_price": 45, "reason": "止盈退出，继续观察"})

    assert sale.status_code == 201
    assert client.get("/v1/holdings").json() == []
    targets = client.get("/v1/research/targets").json()
    assert targets == [{"symbol": "01810", "name": "小米集团", "status": "closed_position", "last_activity_at": sale.json()["sold_at"]}]
    assert client.get("/v1/sales", params={"symbol": "01810"}).json()[0]["reason"] == "止盈退出，继续观察"
    assert client.get("/v1/market/history/01810").json()[0]["close"] == 42
    assert client.get("/v1/decisions/context/01810").json()["name"] == "小米集团"

    repurchase = client.post("/v1/holdings", json={"symbol": "01810", "name": "小米集团", "quantity": 20, "average_cost": 44})

    assert repurchase.status_code == 201
    assert client.get("/v1/research/targets").json()[0]["status"] == "active_holding"
    assert client.get("/v1/sales", params={"symbol": "01810"}).json()[0]["id"] == sale.json()["id"]


def test_sale_rejects_quantity_above_position():
    holding = client.post("/v1/holdings", json={"symbol": "600519", "name": "贵州茅台", "quantity": 2, "average_cost": 1000}).json()
    response = client.post(f"/v1/holdings/{holding['id']}/sales", json={"quantity": 3, "sale_price": 1200})
    assert response.status_code == 422
    assert client.get("/v1/holdings").json()[0]["quantity"] == 2


def test_watchlist_is_available_for_research_without_becoming_a_holding():
    created = client.post("/v1/watchlist", json={"symbol": "0700", "name": "腾讯控股"})

    assert created.status_code == 201
    assert client.get("/v1/holdings").json() == []
    assert client.get("/v1/watchlist").json()[0]["symbol"] == "0700"
    assert client.get("/v1/research/targets").json()[0]["status"] == "watchlist"

    updated = client.post("/v1/watchlist", json={"symbol": "0700", "name": "腾讯控股-W"})

    assert updated.status_code == 201
    assert client.get("/v1/watchlist").json()[0]["name"] == "腾讯控股-W"
    assert client.delete("/v1/watchlist/0700").status_code == 204


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


def test_batch_commit_keeps_the_last_duplicate_symbol_from_a_screenshot(monkeypatch):
    monkeypatch.setattr(market_data, "lookup_symbols", lambda names: [{"query": name, "matches": []} for name in names])
    created = client.post("/v1/holding-drafts/batch", json={"items": [
        {"client_row_id": "row-old", "name": "Xiaomi", "quantity": 100, "average_cost": 25},
        {"client_row_id": "row-new", "name": "Xiaomi", "quantity": 200, "average_cost": 26},
    ]}).json()

    response = client.post("/v1/holding-drafts/commit", json={"items": [
        {"draft_id": created[0]["id"], "symbol": "01810", "name": "Xiaomi"},
        {"draft_id": created[1]["id"], "symbol": "01810", "name": "Xiaomi"},
    ]})

    assert response.status_code == 201
    assert len(response.json()) == 1
    assert response.json()[0]["quantity"] == 200
    assert response.json()[0]["average_cost"] == 26
    assert client.get("/v1/holding-drafts").json() == []


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
