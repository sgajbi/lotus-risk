from __future__ import annotations

from app.domain_data_products import (
    LOCAL_PRODUCER_DECLARATION_PATH,
    get_declared_product,
    list_declared_products,
    load_local_producer_declaration,
)


def test_load_local_producer_declaration_uses_repo_native_contract_path() -> None:
    payload = load_local_producer_declaration()

    assert payload["producer_repository"] == "lotus-risk"
    assert LOCAL_PRODUCER_DECLARATION_PATH.name == "lotus-risk-products.v1.json"


def test_list_declared_products_matches_expected_wave() -> None:
    product_names = [product["product_name"] for product in list_declared_products()]

    assert product_names == [
        "RiskMetricsReport",
        "DrawdownAnalyticsReport",
        "RollingRiskMetricsReport",
        "HistoricalRiskAttributionReport",
        "ConcentrationRiskReport",
        "RegimeScenarioPackEvaluation",
    ]


def test_get_declared_product_returns_repo_native_lifecycle_and_route() -> None:
    product = get_declared_product(
        product_name="HistoricalRiskAttributionReport",
        product_version="v1",
    )

    assert product["lifecycle_status"] == "active"
    assert product["current_routes"] == ["/analytics/risk/historical-attribution"]


def test_get_declared_product_rejects_unknown_product() -> None:
    try:
        get_declared_product(product_name="UnknownReport", product_version="v1")
    except ValueError as exc:
        assert "Unknown lotus-risk declared product" in str(exc)
    else:
        raise AssertionError("expected unknown declared product lookup to fail")
