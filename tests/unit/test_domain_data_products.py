from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from app.domain_data_products import (
    LOCAL_PRODUCER_DECLARATION_PATH,
    _resolve_repo_root,
    get_declared_product,
    list_declared_products,
    load_local_producer_declaration,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_CONSUMER_DECLARATION_PATH = (
    REPO_ROOT / "contracts" / "domain-data-products" / "lotus-risk-consumers.v1.json"
)


def _consumer_dependencies() -> dict[str, dict[str, object]]:
    payload = json.loads(LOCAL_CONSUMER_DECLARATION_PATH.read_text(encoding="utf-8"))
    return {
        str(dependency["product_name"]): dependency
        for dependency in payload["dependencies"]
        if isinstance(dependency, dict)
    }


def test_load_local_producer_declaration_uses_repo_native_contract_path() -> None:
    payload = load_local_producer_declaration()

    assert payload["producer_repository"] == "lotus-risk"
    assert LOCAL_PRODUCER_DECLARATION_PATH.name == "lotus-risk-products.v1.json"


def test_resolve_repo_root_honors_packaged_runtime_location(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOTUS_REPO_ROOT", str(tmp_path / "runtime-root"))

    assert _resolve_repo_root() == (tmp_path / "runtime-root").resolve()


def test_list_declared_products_matches_expected_wave() -> None:
    product_names = [product["product_name"] for product in list_declared_products()]

    assert product_names == [
        "RiskMetricsReport",
        "DrawdownAnalyticsReport",
        "RollingRiskMetricsReport",
        "HistoricalRiskAttributionReport",
        "ConcentrationRiskReport",
        "MandateRiskHealthContext",
        "RegimeScenarioPackEvaluation",
        "RiskEventAffectedCohort",
    ]


def test_get_declared_product_returns_repo_native_lifecycle_and_route() -> None:
    product = get_declared_product(
        product_name="HistoricalRiskAttributionReport",
        product_version="v1",
    )

    assert product["lifecycle_status"] == "active"
    assert product["current_routes"] == ["/analytics/risk/historical-attribution"]


def test_regime_scenario_pack_declaration_tracks_position_identifiers() -> None:
    product = get_declared_product(
        product_name="RegimeScenarioPackEvaluation",
        product_version="v1",
    )

    assert product["approved_consumers"] == ["lotus-gateway", "lotus-manage", "lotus-idea"]
    assert product["identifier_refs"] == ["portfolio_id", "instrument_id"]


def test_mandate_risk_health_context_declaration_is_manage_consumable() -> None:
    product = get_declared_product(
        product_name="MandateRiskHealthContext",
        product_version="v1",
    )

    assert product["current_routes"] == ["/analytics/risk/mandate-health-context"]
    assert product["approved_consumers"] == ["lotus-gateway", "lotus-manage", "lotus-idea"]
    assert product["completeness_policy"] == {
        "default_status": "partial",
        "partial_allowed": True,
    }


def test_concentration_risk_report_declaration_is_idea_consumable() -> None:
    product = get_declared_product(
        product_name="ConcentrationRiskReport",
        product_version="v1",
    )

    assert product["current_routes"] == ["/analytics/risk/concentration"]
    assert product["approved_consumers"] == ["lotus-gateway", "lotus-idea"]
    assert "correlation_id" in product["required_trust_metadata"]
    assert product["lineage_policy"]["evidence_access_class_ref"] == "customer_consumable"


def test_get_declared_product_rejects_unknown_product() -> None:
    try:
        get_declared_product(product_name="UnknownReport", product_version="v1")
    except ValueError as exc:
        assert "Unknown lotus-risk declared product" in str(exc)
    else:
        raise AssertionError("expected unknown declared product lookup to fail")


def test_stateful_sharpe_risk_free_dependency_is_direct_lotus_core_source() -> None:
    dependencies = _consumer_dependencies()

    returns_bundle = dependencies["ReturnsSeriesBundle"]
    assert returns_bundle["producer_repository"] == "lotus-performance"
    assert "portfolio and benchmark return observations" in str(returns_bundle["business_purpose"])

    risk_free_window = dependencies["RiskFreeSeriesWindow"]
    assert risk_free_window["producer_repository"] == "lotus-core"
    assert "stateful Sharpe" in str(risk_free_window["business_purpose"])
    assert risk_free_window["consumption_mode"] == "api_read"
