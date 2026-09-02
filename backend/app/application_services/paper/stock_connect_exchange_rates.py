"""Acquire and normalize SSE Stock Connect reference/settlement exchange rates.

The official SSE tables expose directional RMB-per-HKD ratios.  This service
uses AKShare only as a bounded acquisition adapter for those SSE tables and
persists the normalized observations locally before any execution consumer may
use them.  It never derives a midpoint and never creates a generic FX balance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import math
from typing import Callable

from app.time_utils import beijing_now


BEIJING_TZ = timezone(timedelta(hours=8))
REFERENCE_SOURCE = "http://www.sse.com.cn/services/hkexsc/disclo/ratios/"
SETTLEMENT_SOURCE = "http://www.sse.com.cn/services/hkexsc/disclo/ratios"


@dataclass(frozen=True, slots=True)
class StockConnectExchangeRateObservation:
    kind: str
    applicable_date: str
    pair: str
    currency: str
    buy_rate: float
    sell_rate: float
    settlement_channel: str
    provider: str
    provider_version: str | None
    upstream: str
    source_reference: str
    retrieved_at: str


class AkshareSseStockConnectExchangeRateProvider:
    """Thin adapter around the two documented SSE Stock Connect AKShare calls."""

    def __init__(
        self,
        *,
        reference_fetcher: Callable[[], object] | None = None,
        settlement_fetcher: Callable[[], object] | None = None,
        now_provider: Callable[[], datetime] = beijing_now,
    ) -> None:
        self.reference_fetcher = reference_fetcher
        self.settlement_fetcher = settlement_fetcher
        self.now_provider = now_provider

    @staticmethod
    def _records(frame: object) -> list[dict[str, object]]:
        if frame is None:
            return []
        if isinstance(frame, list):
            return [dict(item) for item in frame if isinstance(item, dict)]
        to_dict = getattr(frame, "to_dict", None)
        if not callable(to_dict):
            raise ValueError("stock_connect_exchange_rate_frame_invalid")
        records = to_dict(orient="records")
        return [dict(item) for item in records if isinstance(item, dict)]

    @staticmethod
    def _date_text(value: object) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value or "").strip().replace("/", "-")
        if not text:
            raise ValueError("stock_connect_exchange_rate_date_missing")
        try:
            return datetime.fromisoformat(text[:10]).date().isoformat()
        except ValueError as error:
            raise ValueError("stock_connect_exchange_rate_date_invalid") from error

    @staticmethod
    def _positive_rate(value: object) -> float:
        try:
            rate = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("stock_connect_exchange_rate_value_invalid") from error
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("stock_connect_exchange_rate_value_invalid")
        return rate

    def _latest_hkd(
        self,
        frame: object,
        *,
        kind: str,
        buy_column: str,
        sell_column: str,
        source_reference: str,
        provider_version: str | None,
    ) -> StockConnectExchangeRateObservation:
        candidates: list[tuple[str, dict[str, object]]] = []
        for row in self._records(frame):
            if str(row.get("货币种类") or "").strip().upper() != "HKD":
                continue
            applicable_date = self._date_text(row.get("适用日期"))
            candidates.append((applicable_date, row))
        if not candidates:
            raise ValueError("stock_connect_hkd_exchange_rate_missing")
        applicable_date, row = max(candidates, key=lambda item: item[0])
        retrieved_at = self.now_provider()
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=BEIJING_TZ)
        else:
            retrieved_at = retrieved_at.astimezone(BEIJING_TZ)
        return StockConnectExchangeRateObservation(
            kind=kind,
            applicable_date=applicable_date,
            pair="HKD/CNY",
            currency="HKD",
            buy_rate=self._positive_rate(row.get(buy_column)),
            sell_rate=self._positive_rate(row.get(sell_column)),
            settlement_channel="SH_HK_CONNECT_RMB",
            provider="AKShare",
            provider_version=provider_version,
            upstream="SSE",
            source_reference=source_reference,
            retrieved_at=retrieved_at.isoformat(),
        )

    def fetch_reference(self) -> StockConnectExchangeRateObservation:
        provider_version = None
        fetcher = self.reference_fetcher
        if fetcher is None:
            import akshare as ak

            provider_version = str(getattr(ak, "__version__", "") or "") or None
            fetcher = ak.stock_sgt_reference_exchange_rate_sse
        return self._latest_hkd(
            fetcher(),
            kind="REFERENCE",
            buy_column="参考汇率买入价",
            sell_column="参考汇率卖出价",
            source_reference=REFERENCE_SOURCE,
            provider_version=provider_version,
        )

    def fetch_settlement(self) -> StockConnectExchangeRateObservation:
        provider_version = None
        fetcher = self.settlement_fetcher
        if fetcher is None:
            import akshare as ak

            provider_version = str(getattr(ak, "__version__", "") or "") or None
            fetcher = ak.stock_sgt_settlement_exchange_rate_sse
        return self._latest_hkd(
            fetcher(),
            kind="SETTLEMENT",
            buy_column="买入结算汇兑比率",
            sell_column="卖出结算汇兑比率",
            source_reference=SETTLEMENT_SOURCE,
            provider_version=provider_version,
        )


class StockConnectExchangeRateService:
    def __init__(self, repository, *, provider=None, now_provider: Callable[[], datetime] = beijing_now) -> None:
        self.repository = repository
        self.provider = provider or AkshareSseStockConnectExchangeRateProvider(now_provider=now_provider)
        self.now_provider = now_provider

    def latest_reference(self, *, applicable_date: str | None = None) -> dict[str, object] | None:
        return self.repository.latest("REFERENCE", applicable_date=applicable_date)

    def latest_settlement(self, *, applicable_date: str | None = None) -> dict[str, object] | None:
        return self.repository.latest("SETTLEMENT", applicable_date=applicable_date)

    def status(self) -> dict[str, object]:
        now = self.now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=BEIJING_TZ)
        else:
            now = now.astimezone(BEIJING_TZ)
        today = now.date().isoformat()
        return {
            "settlement_channel": "SH_HK_CONNECT_RMB",
            "pair": "HKD/CNY",
            "applicable_date": today,
            "reference": self.latest_reference(applicable_date=today),
            "latest_settlement": self.latest_settlement(),
            "usage_scope": "STOCK_CONNECT_EXECUTION_INPUT",
            "generic_fx_cache": False,
        }

    def refresh(self) -> dict[str, object]:
        """Refresh reference and settlement observations independently.

        A partial provider failure never overwrites or fabricates the other fact.
        Consumers continue to read the last persisted immutable snapshot and
        remain fail-closed when today's required reference observation is absent.
        """

        result: dict[str, object] = {
            "settlement_channel": "SH_HK_CONNECT_RMB",
            "pair": "HKD/CNY",
            "reference": None,
            "settlement": None,
            "errors": [],
        }
        for key, fetch in (
            ("reference", self.provider.fetch_reference),
            ("settlement", self.provider.fetch_settlement),
        ):
            try:
                observation = fetch()
                payload = asdict(observation)
                snapshot_id = self.repository.save(payload)
                result[key] = {**payload, "snapshot_id": snapshot_id}
            except Exception as error:
                result["errors"].append(
                    {
                        "kind": key.upper(),
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
        result["status"] = "ok" if not result["errors"] else (
            "partial" if result["reference"] is not None or result["settlement"] is not None else "failed"
        )
        return result


__all__ = [
    "AkshareSseStockConnectExchangeRateProvider",
    "StockConnectExchangeRateObservation",
    "StockConnectExchangeRateService",
]
