from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI

from app.contracts.audit import AuditMetadataFields
from app.trust_telemetry import (
    DeclaredConsumerDependencyTelemetry,
    DeclaredProductTrustTelemetrySnapshot,
    DependencyTelemetrySignal,
    ProductTrustTelemetrySeed,
    TrustTelemetryReviewSummary,
    build_declared_product_trust_telemetry_snapshot,
    build_product_trust_telemetry_seed,
)
from app.trust_telemetry_snapshot_examples import (
    DECLARED_DEPENDENCY_EXAMPLES,
    PRODUCT_TRUST_TELEMETRY_SEED_EXAMPLES,
    TRUST_TELEMETRY_SUMMARY_EXAMPLE,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = REPO_ROOT.parent / "lotus-platform"
TELEMETRY_DIR = REPO_ROOT / "contracts" / "trust-telemetry"
SNAPSHOT_PATH = TELEMETRY_DIR / "risk-metrics-report.telemetry.v1.json"
DECLARATION_PATH = REPO_ROOT / "contracts" / "domain-data-products" / "lotus-risk-products.v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_platform_validator() -> ModuleType:
    validator_path = PLATFORM_ROOT / "automation" / "validate_trust_telemetry.py"
    if not validator_path.exists():
        pytest.skip("lotus-platform trust telemetry validator is not available")
    automation_path = str(PLATFORM_ROOT / "automation")
    if automation_path not in sys.path:
        sys.path.insert(0, automation_path)
    return importlib.import_module("validate_trust_telemetry")


def test_risk_metrics_report_trust_telemetry_validates_with_platform_contract() -> None:
    validator = _load_platform_validator()

    issues = validator.validate_trust_telemetry_path(
        TELEMETRY_DIR,
        catalog_path=PLATFORM_ROOT / "generated" / "domain-product-catalog.json",
    )

    assert issues == []


def test_risk_metrics_report_trust_telemetry_is_tied_to_repo_declaration() -> None:
    snapshot = _load_json(SNAPSHOT_PATH)
    declaration = _load_json(DECLARATION_PATH)
    declared_product = next(
        product
        for product in declaration["products"]
        if product["product_name"] == "RiskMetricsReport"
    )

    assert snapshot["product_id"] == "lotus-risk:RiskMetricsReport:v1"
    assert snapshot["producer_repository"] == declaration["producer_repository"]
    assert snapshot["product_name"] == declared_product["product_name"]
    assert snapshot["product_version"] == declared_product["product_version"]
    assert (
        snapshot["freshness"]["freshness_class"]
        == (declared_product["freshness_policy"]["freshness_class"])
    )
    assert set(snapshot["observed_trust_metadata"]) == set(
        declared_product["required_trust_metadata"]
    )
    assert snapshot["lineage"]["lineage_materialized"] is True
    assert (
        snapshot["lineage"]["evidence_access_class"]
        == (declared_product["lineage_policy"]["evidence_access_class_ref"])
    )
    assert snapshot["blocking"]["blocked"] is False


def test_trust_telemetry_facade_preserves_public_imports() -> None:
    assert ProductTrustTelemetrySeed.__name__ == "ProductTrustTelemetrySeed"
    assert DependencyTelemetrySignal.__name__ == "DependencyTelemetrySignal"
    assert DeclaredConsumerDependencyTelemetry.__name__ == "DeclaredConsumerDependencyTelemetry"
    assert TrustTelemetryReviewSummary.__name__ == "TrustTelemetryReviewSummary"
    assert DeclaredProductTrustTelemetrySnapshot.__name__ == "DeclaredProductTrustTelemetrySnapshot"
    assert callable(build_product_trust_telemetry_seed)
    assert callable(build_declared_product_trust_telemetry_snapshot)


def test_trust_telemetry_snapshot_schema_uses_governed_examples() -> None:
    schema = DeclaredProductTrustTelemetrySnapshot.model_json_schema()
    properties = schema["properties"]

    assert properties["declared_dependencies"]["example"] == DECLARED_DEPENDENCY_EXAMPLES
    assert properties["summary"]["example"] == TRUST_TELEMETRY_SUMMARY_EXAMPLE
    assert properties["products"]["example"] == PRODUCT_TRUST_TELEMETRY_SEED_EXAMPLES


def test_build_product_trust_telemetry_seed_uses_runtime_and_lineage_inputs() -> None:
    app = FastAPI()
    app.state.is_draining = False
    app.state.dependency_statuses = {
        "lotus-performance": {
            "status": "degraded",
            "detail": "benchmark context delayed",
            "category": "data_gap",
            "issue_code": "BENCHMARK_CONTEXT_DELAYED",
        }
    }
    metadata = AuditMetadataFields(
        request_fingerprint="sha256:test",
        source_services=["lotus-risk", "lotus-performance"],
        upstream_request_fingerprints={
            "lotus-performance:/integration/returns/series": "sha256:upstream"
        },
    )

    seed = build_product_trust_telemetry_seed(
        app=app,
        product_name="RiskMetricsReport",
        product_version="v1",
        metadata=metadata,
    )

    assert seed.product_name == "RiskMetricsReport"
    assert seed.product_version == "v1"
    assert seed.authoritative_domain == "risk_analytics"
    assert seed.product_family == "analytics_output"
    assert seed.approved_consumers == ["lotus-gateway"]
    assert "request_fingerprint" in seed.required_trust_metadata
    assert seed.lifecycle_status == "active"
    assert seed.current_routes == ["/analytics/risk/calculate"]
    assert seed.readiness_status == "degraded"
    assert seed.ops_status == "degraded"
    assert seed.draining is False
    assert seed.lineage_version == "risk_audit_lineage.v1"
    assert seed.request_fingerprint == "sha256:test"
    assert seed.source_services == ["lotus-risk", "lotus-performance"]
    assert seed.upstream_request_fingerprints == {
        "lotus-performance:/integration/returns/series": "sha256:upstream"
    }
    assert [signal.service for signal in seed.dependency_signals] == [
        "lotus-core",
        "lotus-performance",
    ]
    assert seed.dependency_signals[1].status == "degraded"
    assert seed.dependency_signals[1].category == "data_gap"
    assert seed.dependency_signals[1].issue_code == "BENCHMARK_CONTEXT_DELAYED"
    assert seed.emitted_at.endswith("Z")


def test_build_product_trust_telemetry_seed_preserves_draining_and_missing_lineage() -> None:
    app = FastAPI()
    app.state.is_draining = True

    seed = build_product_trust_telemetry_seed(
        app=app,
        product_name="ConcentrationRiskReport",
        product_version="v1",
    )

    assert seed.product_name == "ConcentrationRiskReport"
    assert seed.readiness_status == "draining"
    assert seed.ops_status == "degraded"
    assert seed.draining is True
    assert seed.lineage_version is None
    assert seed.request_fingerprint is None
    assert seed.source_services == []
    assert seed.upstream_request_fingerprints == {}


def test_build_product_trust_telemetry_seed_rejects_undeclared_products() -> None:
    app = FastAPI()

    try:
        build_product_trust_telemetry_seed(
            app=app,
            product_name="UncataloguedRiskReport",
            product_version="v1",
        )
    except ValueError as exc:
        assert "Unknown lotus-risk declared product" in str(exc)
    else:
        raise AssertionError("expected undeclared product telemetry seed build to fail")


def test_build_declared_product_trust_telemetry_snapshot_uses_repo_native_catalog() -> None:
    app = FastAPI()
    app.state.dependency_statuses = {
        "lotus-core": {
            "status": "degraded",
            "detail": "risk-free source stale",
            "category": "data_gap",
            "issue_code": "RISK_FREE_SERIES_STALE",
        }
    }

    snapshot = build_declared_product_trust_telemetry_snapshot(
        app=app,
        service_name="lotus-risk",
    )

    assert snapshot.service == "lotus-risk"
    assert (
        snapshot.declaration_source == "contracts/domain-data-products/lotus-risk-products.v1.json"
    )
    assert snapshot.declaration_fingerprint.startswith("sha256:")
    assert (
        snapshot.consumer_declaration_source
        == "contracts/domain-data-products/lotus-risk-consumers.v1.json"
    )
    assert snapshot.consumer_declaration_fingerprint.startswith("sha256:")
    assert [dependency.product_name for dependency in snapshot.declared_dependencies] == [
        "ReturnsSeriesBundle",
        "BenchmarkExposureContext",
        "PortfolioStateSnapshot",
        "PositionTimeseriesInput",
        "InstrumentReferenceBundle",
        "RiskFreeSeriesWindow",
    ]
    assert snapshot.declared_dependencies[0].producer_repository == "lotus-performance"
    assert "correlation_id" in snapshot.declared_dependencies[0].required_trust_metadata
    assert snapshot.declared_dependencies[0].runtime_status == "ok"
    assert snapshot.declared_dependencies[2].runtime_status == "degraded"
    assert snapshot.declared_dependencies[2].runtime_category == "data_gap"
    assert snapshot.declared_dependencies[2].runtime_issue_code == "RISK_FREE_SERIES_STALE"
    assert snapshot.summary.declared_product_count == 8
    assert snapshot.summary.declared_dependency_count == 6
    assert snapshot.summary.degraded_dependency_count == 4
    assert snapshot.summary.unavailable_dependency_count == 0
    assert snapshot.summary.missing_runtime_service_count == 0
    assert snapshot.summary.degraded_dependency_products == [
        "PortfolioStateSnapshot",
        "PositionTimeseriesInput",
        "InstrumentReferenceBundle",
        "RiskFreeSeriesWindow",
    ]
    assert snapshot.summary.unavailable_dependency_products == []
    assert snapshot.summary.missing_runtime_services == []
    assert [product.product_name for product in snapshot.products] == [
        "RiskMetricsReport",
        "DrawdownAnalyticsReport",
        "RollingRiskMetricsReport",
        "HistoricalRiskAttributionReport",
        "ConcentrationRiskReport",
        "MandateRiskHealthContext",
        "RegimeScenarioPackEvaluation",
        "RiskEventAffectedCohort",
    ]
    assert all(product.lifecycle_status == "active" for product in snapshot.products)
    assert snapshot.products[0].product_family == "analytics_output"
    assert snapshot.products[0].approved_consumers == ["lotus-gateway"]
    assert snapshot.products[0].current_routes == ["/analytics/risk/calculate"]
    assert snapshot.products[0].dependency_signals[0].issue_code == "RISK_FREE_SERIES_STALE"
