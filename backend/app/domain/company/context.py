"""Company Intelligence research-domain contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


COMPANY_CONTEXT_VERSION = "company-context-v1"
USAGE_SCOPE = "RESEARCH_ONLY"


@dataclass(frozen=True)
class CompanyDatasetRef:
    dataset_key: str
    data_type: str
    snapshot_id: str
    payload_hash: str
    provider: str
    as_of: str
    available_at: str
    freshness_status: str


@dataclass(frozen=True)
class CompanyContext:
    symbol: str
    name: str
    research_priority: str
    analysis_depth: str
    generated_at: str
    datasets: Mapping[str, Any]
    dataset_refs: tuple[CompanyDatasetRef, ...]
    missing_datasets: tuple[str, ...] = ()
    stale_datasets: tuple[str, ...] = ()
    version: str = COMPANY_CONTEXT_VERSION
    usage_scope: str = USAGE_SCOPE
    formal_trade_authority: bool = False

    @property
    def research_ready(self) -> bool:
        return not self.missing_datasets

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["research_ready"] = self.research_ready
        return result


@dataclass(frozen=True)
class CompanyDatasetSpec:
    key: str
    data_type: str
    max_age_seconds: int
    schema_version: str
    description: str
    required_for_priorities: tuple[str, ...]


DATASET_SPECS: tuple[CompanyDatasetSpec, ...] = (
    CompanyDatasetSpec("identity_business_model", "company_identity_business_model", 30 * 86_400, "company-identity-v1", "公司身份、商业模式、主要产品与业务线", ("L0", "L1", "L2", "L3", "L4")),
    CompanyDatasetSpec("products_segments", "company_products_segments", 14 * 86_400, "company-segments-v1", "产品线、业务分部、收入结构与关键经营指标", ("L1", "L2", "L3", "L4")),
    CompanyDatasetSpec("financial_summary", "company_financial_summary", 7 * 86_400, "company-financial-summary-v1", "收入、利润、现金流及报告期/公告时点", ("L2", "L3", "L4")),
    CompanyDatasetSpec("margin_structure", "company_margin_structure", 7 * 86_400, "company-margin-v1", "综合与分部毛利/毛利率、利润来源及变化驱动", ("L2", "L3", "L4")),
    CompanyDatasetSpec("profit_cashflow_drivers", "company_profit_cashflow_drivers", 7 * 86_400, "company-profit-drivers-v1", "盈利与现金流驱动因素、经营杠杆和关键敏感项", ("L3", "L4")),
    CompanyDatasetSpec("industry_competition", "company_industry_competition", 14 * 86_400, "company-industry-v1", "行业位置、主要竞争者、竞争优势与结构性风险", ("L3", "L4")),
    CompanyDatasetSpec("management_capital_allocation", "company_management_capital_allocation", 30 * 86_400, "company-management-v1", "管理层、资本配置、回购分红融资及治理事项", ("L3", "L4")),
    CompanyDatasetSpec("risks_catalysts", "company_risks_catalysts", 86_400, "company-risks-catalysts-v1", "可追溯风险、催化剂、公告和事件验证条件", ("L2", "L3", "L4")),
    CompanyDatasetSpec("valuation_framework", "company_valuation_framework", 7 * 86_400, "company-valuation-v1", "估值输入与框架；研究用途，不直接成为 OPEN 阈值", ("L3", "L4")),
)


def required_dataset_specs(research_priority: str) -> tuple[CompanyDatasetSpec, ...]:
    priority = str(research_priority or "L1").strip().upper()
    if priority not in {"L0", "L1", "L2", "L3", "L4"}:
        raise ValueError(f"unsupported research priority: {research_priority}")
    return tuple(spec for spec in DATASET_SPECS if priority in spec.required_for_priorities)


def analysis_depth_for_priority(research_priority: str) -> str:
    priority = str(research_priority or "L1").strip().upper()
    if priority in {"L3", "L4"}:
        return "deep_company"
    if priority == "L2":
        return "focused_company"
    return "basic_company"
