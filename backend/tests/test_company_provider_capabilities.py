from app.application_services.company.akshare_provider import CompanyAkshareProvider
from app.application_services.company.provider_registry import CompanyDataProviderRegistry


def _registry():
    registry = CompanyDataProviderRegistry()
    CompanyAkshareProvider().register(registry)
    return registry


def test_a_share_segment_and_margin_datasets_are_supported():
    registry = _registry()

    assert registry.supports("company_products_segments", "600519") is True
    assert registry.supports("company_margin_structure", "600519") is True


def test_hk_segment_dataset_is_explicitly_unsupported_without_remote_retry():
    registry = _registry()

    assert registry.supports("company_products_segments", "01810") is False
    assert registry.supports("company_financial_summary", "01810") is True
    assert registry.supports("company_margin_structure", "01810") is True
    assert registry.supports("company_industry_competition", "01810") is True


def test_unregistered_company_dataset_is_unsupported():
    registry = _registry()

    assert registry.supports("company_management_capital_allocation", "600519") is False
