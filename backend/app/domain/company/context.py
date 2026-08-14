"""Company Intelligence research-domain contracts.

Company context is a structured research snapshot.  It can explain why a
business is interesting, what drives revenue/margins/profit, and which conditions
invalidate a thesis, but it never grants formal trade authority by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    coverage_keys: tuple[str, ...] = ()


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
    required_for_priorities: tuple[str, ...] = field(default_factory=tuple)


DATASET_SPECS: tuple[CompanyDatasetSpec, ...] = (
    CompanyDatasetSpec(
        key="identity_business_model",
        data_type="company_identity_business_model",
        max_age_seconds=30 * 86_400,
        schema_version="company-identity-v1",
        description="公司身份、商业模式、主要产品与业务线",
        required_for_priorities=("L0", "L1", "L2", "L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="products_segments",
        data_type="company_products_segments",
        max_age_seconds=14 * 86_400,
        schema_version="company-segments-v1",
        description="产品线、业务分部、收入结构与关键经营指标",
        required_for_priorities=("L1", "L2", "L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="financial_summary",
        data_type="company_financial_summary",
        max_age_seconds=7 * 86_400,
        schema_version="company-financial-summary-v1",
        description="收入、利润、现金流及报告期/公告时点",
        required_for_priorities=("L2", "L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="margin_structure",
        data_type="company_margin_structure",
        max_age_seconds=7 * 86_400,
        schema_version="company-margin-v1",
        description="综合与分部毛利/毛利率、利润来源及变化驱动",
        required_for_priorities=("L2", "L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="profit_cashflow_drivers",
        data_type="company_profit_cashflow_drivers",
        max_age_seconds=7 * 86_400,
        schema_version="company-profit-drivers-v1",
        description="盈利与现金流驱动因素、经营杠杆和关键敏感项",
        required_for_priorities=("L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="industry_competition",
        data_type="company_industry_competition",
        max_age_seconds=14 * 86_400,
        schema_version="company-industry-v1",
        description="行业位置、主要竞争者、竞争优势与结构性风险",
        required_for_priorities=("L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="management_capital_allocation",
        data_type="company_management_capital_allocation",
        max_age_seconds=30 * 86_400,
        schema_version="company-management-v1",
        description="管理层、资本配置、回购分红融资及治理事项",
        required_for_priorities=("L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="risks_catalysts",
        data_type="company_risks_catalysts",
        max_age_seconds=86_400,
        schema_version="company-risks-catalysts-v1",
        description="可追溯风险、催化剂、公告和事件验证条件",
        required_for_priorities=("L2", "L3", "L4"),
    ),
    CompanyDatasetSpec(
        key="valuation_framework",
        data_type="company_valuation_framework",
        max_age_seconds=7 * 86_400,
        schema_version="company-valuation-v1",
        description="估值输入与框架；研究用途，不直接成为 OPEN 阈值",
        required_for_priorities=("L3", "L4"),
    ),
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
