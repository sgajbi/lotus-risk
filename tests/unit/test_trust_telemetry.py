from __future__ import annotations

from fastapi import FastAPI

from app.contracts.audit import AuditMetadataFields
from app.trust_telemetry import build_product_trust_telemetry_seed


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
    assert seed.lifecycle_status == "active"
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
