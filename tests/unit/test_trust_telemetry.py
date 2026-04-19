from __future__ import annotations

from fastapi import FastAPI

from app.contracts.audit import AuditMetadataFields
from app.trust_telemetry import (
    build_declared_product_trust_telemetry_snapshot,
    build_product_trust_telemetry_seed,
)


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
    assert snapshot.declaration_source == "contracts/domain-data-products/lotus-risk-products.v1.json"
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
    assert [product.product_name for product in snapshot.products] == [
        "RiskMetricsReport",
        "DrawdownAnalyticsReport",
        "RollingRiskMetricsReport",
        "HistoricalRiskAttributionReport",
        "ConcentrationRiskReport",
    ]
    assert all(product.lifecycle_status == "active" for product in snapshot.products)
    assert snapshot.products[0].product_family == "analytics_output"
    assert snapshot.products[0].approved_consumers == ["lotus-gateway"]
    assert snapshot.products[0].current_routes == ["/analytics/risk/calculate"]
    assert snapshot.products[0].dependency_signals[0].issue_code == "RISK_FREE_SERIES_STALE"
