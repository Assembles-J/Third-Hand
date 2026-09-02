from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.paper.router import create_paper_schedule_router
from app.application_services.paper.stock_connect_exchange_rates import (
    AkshareSseStockConnectExchangeRateProvider,
    StockConnectExchangeRateService,
)
from app.infrastructure.database.stock_connect_exchange_rate_repository import (
    StockConnectExchangeRateRepository,
)
from app.storage import PortfolioStore


CN_TZ = timezone(timedelta(hours=8))


class _Frame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient="records"):
        assert orient == "records"
        return list(self.rows)


def _reference_frame():
    return _Frame(
        [
            {"适用日期": "2026-09-01", "参考汇率买入价": 0.90, "参考汇率卖出价": 0.96, "货币种类": "HKD"},
            {"适用日期": "2026-09-02", "参考汇率买入价": 0.91, "参考汇率卖出价": 0.97, "货币种类": "HKD"},
        ]
    )


def _settlement_frame():
    return _Frame(
        [
            {"适用日期": "2026-09-01", "买入结算汇兑比率": 0.931, "卖出结算汇兑比率": 0.934, "货币种类": "HKD"},
            {"适用日期": "2026-09-02", "买入结算汇兑比率": 0.932, "卖出结算汇兑比率": 0.935, "货币种类": "HKD"},
        ]
    )


def _provider(now):
    return AkshareSseStockConnectExchangeRateProvider(
        reference_fetcher=_reference_frame,
        settlement_fetcher=_settlement_frame,
        now_provider=lambda: now,
    )


def test_akshare_adapter_normalizes_latest_directional_sse_rows() -> None:
    now = datetime(2026, 9, 2, 9, 0, tzinfo=CN_TZ)
    provider = _provider(now)

    reference = provider.fetch_reference()
    settlement = provider.fetch_settlement()

    assert reference.kind == "REFERENCE"
    assert reference.applicable_date == "2026-09-02"
    assert reference.pair == "HKD/CNY"
    assert reference.buy_rate == 0.91
    assert reference.sell_rate == 0.97
    assert reference.upstream == "SSE"
    assert reference.settlement_channel == "SH_HK_CONNECT_RMB"
    assert settlement.kind == "SETTLEMENT"
    assert settlement.buy_rate == 0.932
    assert settlement.sell_rate == 0.935


def test_repository_reuses_existing_lineage_and_records_source_revision(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "stock-connect-rates.db")
    repository = StockConnectExchangeRateRepository(store)
    base = {
        "kind": "REFERENCE",
        "applicable_date": "2026-09-02",
        "pair": "HKD/CNY",
        "currency": "HKD",
        "buy_rate": 0.91,
        "sell_rate": 0.97,
        "settlement_channel": "SH_HK_CONNECT_RMB",
        "provider": "AKShare",
        "provider_version": "test",
        "upstream": "SSE",
        "source_reference": "http://www.sse.com.cn/services/hkexsc/disclo/ratios/",
        "retrieved_at": "2026-09-02T09:00:00+08:00",
    }

    first = repository.save(base)
    replay = repository.save(base)
    revised = repository.save({**base, "sell_rate": 0.971, "retrieved_at": "2026-09-02T09:05:00+08:00"})
    latest = repository.latest("REFERENCE", applicable_date="2026-09-02")

    assert replay == first
    assert revised != first
    assert latest is not None
    assert latest["sell_rate"] == 0.971
    assert latest["supersedes_snapshot_id"] == first
    assert latest["snapshot_id"] == revised


def test_service_refresh_persists_reference_and_settlement_without_generic_fx_cache(tmp_path: Path) -> None:
    now = datetime(2026, 9, 2, 9, 0, tzinfo=CN_TZ)
    store = PortfolioStore(tmp_path / "stock-connect-refresh.db")
    service = StockConnectExchangeRateService(
        StockConnectExchangeRateRepository(store),
        provider=_provider(now),
        now_provider=lambda: now,
    )

    refreshed = service.refresh()
    status = service.status()

    assert refreshed["status"] == "ok"
    assert refreshed["errors"] == []
    assert status["generic_fx_cache"] is False
    assert status["reference"]["applicable_date"] == "2026-09-02"
    assert status["reference"]["buy_rate"] == 0.91
    assert status["reference"]["sell_rate"] == 0.97
    assert status["latest_settlement"]["buy_rate"] == 0.932
    assert status["usage_scope"] == "STOCK_CONNECT_EXECUTION_INPUT"

    with store._connect() as connection:
        retired_fx_cache = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fx_rate_cache'"
        ).fetchone()
    assert retired_fx_cache is None


def test_service_refresh_is_partial_when_one_official_table_is_unavailable(tmp_path: Path) -> None:
    now = datetime(2026, 9, 2, 9, 0, tzinfo=CN_TZ)

    def broken_settlement():
        raise RuntimeError("SSE settlement table unavailable")

    provider = AkshareSseStockConnectExchangeRateProvider(
        reference_fetcher=_reference_frame,
        settlement_fetcher=broken_settlement,
        now_provider=lambda: now,
    )
    service = StockConnectExchangeRateService(
        StockConnectExchangeRateRepository(PortfolioStore(tmp_path / "stock-connect-partial.db")),
        provider=provider,
        now_provider=lambda: now,
    )

    refreshed = service.refresh()

    assert refreshed["status"] == "partial"
    assert refreshed["reference"] is not None
    assert refreshed["settlement"] is None
    assert refreshed["errors"][0]["kind"] == "SETTLEMENT"


def test_paper_rate_routes_are_local_read_plus_explicit_bounded_refresh(tmp_path: Path) -> None:
    now = datetime(2026, 9, 2, 9, 0, tzinfo=CN_TZ)
    service = StockConnectExchangeRateService(
        StockConnectExchangeRateRepository(PortfolioStore(tmp_path / "stock-connect-api.db")),
        provider=_provider(now),
        now_provider=lambda: now,
    )
    app = FastAPI()
    app.include_router(
        create_paper_schedule_router(
            lambda: {},
            stock_connect_exchange_rate_service=service,
        )
    )
    client = TestClient(app)

    before = client.get("/v1/paper-trading/stock-connect-rates")
    refreshed = client.post("/v1/paper-trading/stock-connect-rates/refresh")
    after = client.get("/v1/paper-trading/stock-connect-rates")

    assert before.status_code == 200
    assert before.json()["reference"] is None
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "ok"
    assert after.status_code == 200
    assert after.json()["reference"]["applicable_date"] == "2026-09-02"
