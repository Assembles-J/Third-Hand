"""AKShare adapters for persisted Company Intelligence datasets.

These adapters are intentionally narrow and normalize all DataFrame values before
crossing ResearchDataGateway. They provide research evidence only; they never
feed ActionPolicy or PositionSizing directly.
"""
from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any

from app.domain.research.data_gateway import ProviderFetchResult, ResearchDataRequest
from app.time_utils import beijing_now


A_SHARE_TYPES = {
    "company_identity_business_model",
    "company_products_segments",
    "company_financial_summary",
    "company_margin_structure",
    "company_profit_cashflow_drivers",
}
HK_SHARE_TYPES = {
    "company_identity_business_model",
    "company_financial_summary",
    "company_margin_structure",
    "company_profit_cashflow_drivers",
    "company_industry_competition",
    "company_valuation_framework",
}


def _is_hk(symbol: str) -> bool:
    return len(symbol) == 5 and symbol.isdigit()


def _em_symbol(symbol: str) -> str:
    if symbol.startswith(("4", "8", "92")):
        return f"BJ{symbol}"
    if symbol.startswith(("5", "6", "9")):
        return f"SH{symbol}"
    return f"SZ{symbol}"


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        if math.isnan(float(value)):
            return None
    except (TypeError, ValueError):
        pass
    item = getattr(value, "item", None)
    if callable(item):
        try:
            value = item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _records(frame, *, limit: int | None = None) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    values = frame.head(limit) if limit else frame
    return [
        {str(key): _scalar(value) for key, value in record.items()}
        for record in values.to_dict("records")
    ]


def _as_of_from_rows(rows: list[dict[str, Any]], *keys: str) -> str:
    for row in rows:
        for key in keys:
            text = str(row.get(key) or "").strip()
            if not text or text.lower() in {"none", "nan", "nat"}:
                continue
            text = text[:10]
            if len(text) == 8 and text.isdigit():
                text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
            try:
                datetime.fromisoformat(text)
                return f"{text}T00:00:00+08:00"
            except ValueError:
                continue
    return beijing_now().isoformat()


def _hk_report_type(row: dict[str, Any]) -> str:
    """Normalize Eastmoney DATE_TYPE while preserving non-calendar issuers."""
    label = str(row.get("DATE_TYPE") or row.get("REPORT_TYPE") or "").strip().lower()
    if any(token in label for token in ("中报", "中期", "interim", "half")):
        return "interim"
    if any(token in label for token in ("一季", "first quarter", "q1")):
        return "q1"
    if any(token in label for token in ("三季", "third quarter", "q3")):
        return "q3"
    if any(token in label for token in ("年报", "年度", "annual", "final")):
        return "annual"
    # Fallback is used only when provider DATE_TYPE is absent. It is compatible
    # with calendar-year issuers such as Xiaomi while DATE_TYPE remains the
    # preferred authority for non-calendar fiscal years.
    text = str(row.get("REPORT_DATE") or row.get("START_DATE") or "")[:10]
    suffix = text[5:] if len(text) >= 10 else ""
    return {
        "03-31": "q1",
        "06-30": "interim",
        "09-30": "q3",
        "12-31": "annual",
    }.get(suffix, "report_period")


def _hk_report_period_rows(ak, symbol: str, *, limit: int = 12) -> list[dict[str, Any]]:
    # AKShare documents `indicator` as accepting both 年度 and 报告期. Report
    # period is required here so an interim disclosure can become the latest
    # observation instead of a freshly retrieved old annual row.
    rows = _records(
        ak.stock_financial_hk_analysis_indicator_em(symbol=symbol, indicator="报告期"),
        limit=limit,
    )
    enriched = []
    for row in rows:
        item = dict(row)
        item["report_type"] = _hk_report_type(item)
        enriched.append(item)
    return enriched


class CompanyAkshareProvider:
    """Dispatch normalized company datasets to documented AKShare interfaces."""

    provider_name = "AKShare"

    def supports(self, data_type: str, symbol: str) -> bool:
        supported = HK_SHARE_TYPES if _is_hk(str(symbol or "").strip().upper()) else A_SHARE_TYPES
        return str(data_type or "").strip().lower() in supported

    def register(self, registry) -> None:
        for data_type in sorted(A_SHARE_TYPES | HK_SHARE_TYPES):
            registry.register(data_type, self.fetch, supports=self.supports)

    def fetch(self, request: ResearchDataRequest, missing, existing) -> ProviderFetchResult:
        symbol = str(request.symbol or "").strip().upper()
        if not symbol:
            raise ValueError("company_provider_symbol_required")
        if not self.supports(request.data_type, symbol):
            raise ValueError(f"company_dataset_not_supported_for_market:{request.data_type}:{symbol}")

        import akshare as ak

        handler = getattr(self, f"_{request.data_type}")
        payload, as_of, source_reference = handler(ak, symbol)
        if not payload:
            raise ValueError(f"company_provider_empty:{request.data_type}:{symbol}")
        return ProviderFetchResult(
            provider=self.provider_name,
            payload=payload,
            as_of=as_of,
            available_at=beijing_now().isoformat(),
            source_reference=source_reference,
            coverage_keys=(),
            detail={
                "dataset": request.data_type,
                "market": "HK" if _is_hk(symbol) else "CN",
                "normalized": True,
                "usage_scope": "RESEARCH_ONLY",
                "report_period_semantics": "报告期" if _is_hk(symbol) and request.data_type in {
                    "company_financial_summary", "company_margin_structure", "company_profit_cashflow_drivers",
                } else None,
            },
        )

    def _company_identity_business_model(self, ak, symbol: str):
        if _is_hk(symbol):
            rows = _records(ak.stock_hk_company_profile_em(symbol=symbol), limit=1)
            return (
                {"company_profile": rows[0]} if rows else {},
                beijing_now().isoformat(),
                "Eastmoney/AKShare stock_hk_company_profile_em",
            )
        intro = _records(ak.stock_zyjs_ths(symbol=symbol), limit=1)
        info_frame = ak.stock_individual_info_em(symbol=symbol)
        info = {}
        if info_frame is not None and not info_frame.empty:
            for _, row in info_frame.iterrows():
                key = str(row.get("item") or "").strip()
                if key:
                    info[key] = _scalar(row.get("value"))
        return (
            {"profile": info, "business_introduction": intro[0] if intro else None},
            beijing_now().isoformat(),
            "Eastmoney+THS/AKShare stock_individual_info_em+stock_zyjs_ths",
        )

    def _company_products_segments(self, ak, symbol: str):
        rows = _records(ak.stock_zygc_em(symbol=_em_symbol(symbol)))
        if not rows:
            return {}, beijing_now().isoformat(), "Eastmoney/AKShare stock_zygc_em"
        latest_date = max(str(row.get("报告日期") or "")[:10] for row in rows)
        latest = [row for row in rows if str(row.get("报告日期") or "")[:10] == latest_date]
        return (
            {"report_date": latest_date, "segments": latest},
            _as_of_from_rows(latest, "报告日期"),
            "Eastmoney/AKShare stock_zygc_em",
        )

    def _company_financial_summary(self, ak, symbol: str):
        if _is_hk(symbol):
            rows = _hk_report_period_rows(ak, symbol)
            return (
                {"report_period_indicators": rows, "annual_indicators": rows},
                _as_of_from_rows(rows, "REPORT_DATE", "START_DATE"),
                "Eastmoney/AKShare stock_financial_hk_analysis_indicator_em?indicator=报告期",
            )
        rows = _records(ak.stock_financial_analysis_indicator_em(symbol=symbol), limit=8)
        return (
            {"indicators": rows},
            _as_of_from_rows(rows, "REPORT_DATE", "日期"),
            "Eastmoney/AKShare stock_financial_analysis_indicator_em",
        )

    def _company_margin_structure(self, ak, symbol: str):
        if _is_hk(symbol):
            rows = _hk_report_period_rows(ak, symbol)
            margins = [{
                "report_date": row.get("REPORT_DATE") or row.get("START_DATE"),
                "report_type": row.get("report_type"),
                "date_type": row.get("DATE_TYPE"),
                "revenue": row.get("OPERATE_INCOME"),
                "gross_profit": row.get("GROSS_PROFIT"),
                "gross_margin_percent": row.get("GROSS_PROFIT_RATIO"),
                "net_margin_percent": row.get("NET_PROFIT_RATIO"),
            } for row in rows]
            return (
                {"company_margin_history": margins, "segment_margin_available": False},
                _as_of_from_rows(rows, "REPORT_DATE", "START_DATE"),
                "Eastmoney/AKShare stock_financial_hk_analysis_indicator_em?indicator=报告期",
            )
        rows = _records(ak.stock_zygc_em(symbol=_em_symbol(symbol)))
        latest_date = max((str(row.get("报告日期") or "")[:10] for row in rows), default="")
        latest = [row for row in rows if str(row.get("报告日期") or "")[:10] == latest_date]
        return (
            {"report_date": latest_date, "segment_margins": latest},
            _as_of_from_rows(latest, "报告日期"),
            "Eastmoney/AKShare stock_zygc_em",
        )

    def _company_profit_cashflow_drivers(self, ak, symbol: str):
        if _is_hk(symbol):
            rows = _hk_report_period_rows(ak, symbol)
            drivers = [{
                "report_date": row.get("REPORT_DATE") or row.get("START_DATE"),
                "report_type": row.get("report_type"),
                "date_type": row.get("DATE_TYPE"),
                "revenue": row.get("OPERATE_INCOME"),
                "revenue_yoy_percent": row.get("OPERATE_INCOME_YOY"),
                "gross_profit": row.get("GROSS_PROFIT"),
                "gross_profit_yoy_percent": row.get("GROSS_PROFIT_YOY"),
                "holder_profit": row.get("HOLDER_PROFIT"),
                "holder_profit_yoy_percent": row.get("HOLDER_PROFIT_YOY"),
                "operating_cashflow_to_sales_percent": row.get("OCF_SALES"),
                "roe_percent": row.get("ROE_AVG"),
                "roic_percent": row.get("ROIC_YEARLY"),
            } for row in rows]
            return (
                {
                    # Compatibility key retained while the payload now contains
                    # all report periods rather than annual-only observations.
                    "annual_driver_history": drivers,
                    "report_period_driver_history": drivers,
                },
                _as_of_from_rows(rows, "REPORT_DATE", "START_DATE"),
                "Eastmoney/AKShare stock_financial_hk_analysis_indicator_em?indicator=报告期",
            )
        rows = _records(ak.stock_financial_analysis_indicator_em(symbol=symbol), limit=8)
        return (
            {"indicator_history": rows},
            _as_of_from_rows(rows, "REPORT_DATE", "日期"),
            "Eastmoney/AKShare stock_financial_analysis_indicator_em",
        )

    def _company_industry_competition(self, ak, symbol: str):
        rows = _records(ak.stock_hk_growth_comparison_em(symbol=symbol), limit=30)
        return (
            {"growth_peer_comparison": rows},
            beijing_now().isoformat(),
            "Eastmoney/AKShare stock_hk_growth_comparison_em",
        )

    def _company_valuation_framework(self, ak, symbol: str):
        rows = _records(ak.stock_hk_valuation_comparison_em(symbol=symbol), limit=30)
        return (
            {"valuation_peer_comparison": rows},
            beijing_now().isoformat(),
            "Eastmoney/AKShare stock_hk_valuation_comparison_em",
        )
