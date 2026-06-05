from __future__ import annotations

from typing import Any

DECLARED_DEPENDENCY_EXAMPLES: list[Any] = [
    {
        "product_name": "ReturnsSeriesBundle",
        "producer_repository": "lotus-performance",
        "required_product_version": "v1",
        "consumption_mode": "api_read",
        "failure_posture": "fail_closed",
        "validation_lanes": ["feature", "pr-merge"],
        "required_trust_metadata": [
            "generated_at",
            "as_of_date",
            "correlation_id",
        ],
        "runtime_status": "degraded",
        "runtime_detail": "high_latency",
        "runtime_category": "transport",
        "runtime_issue_code": "UPSTREAM_HIGH_LATENCY",
    }
]

TRUST_TELEMETRY_SUMMARY_EXAMPLE: dict[str, Any] = {
    "declared_product_count": 7,
    "declared_dependency_count": 6,
    "degraded_dependency_count": 2,
    "unavailable_dependency_count": 0,
    "missing_runtime_service_count": 0,
    "degraded_dependency_products": [
        "ReturnsSeriesBundle",
        "BenchmarkExposureContext",
    ],
    "unavailable_dependency_products": [],
    "missing_runtime_services": [],
}

PRODUCT_TRUST_TELEMETRY_SEED_EXAMPLES: list[Any] = [
    {
        "product_name": "RiskMetricsReport",
        "product_version": "v1",
        "authoritative_domain": "risk_analytics",
        "product_family": "analytics_output",
        "approved_consumers": ["lotus-gateway"],
        "required_trust_metadata": [
            "product_name",
            "product_version",
            "as_of_date",
            "lineage_version",
            "request_fingerprint",
        ],
        "lifecycle_status": "active",
        "current_routes": ["/analytics/risk/calculate"],
        "emitted_at": "2026-04-19T00:00:00Z",
        "readiness_status": "degraded",
        "ops_status": "degraded",
        "draining": False,
        "lineage_version": "risk_audit_lineage.v1",
        "request_fingerprint": ("sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c"),
        "source_services": ["lotus-risk", "lotus-performance"],
        "upstream_request_fingerprints": {
            "lotus-performance:/integration/returns/series": (
                "sha256:8d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a1"
            )
        },
        "dependency_signals": [
            {
                "service": "lotus-performance",
                "status": "degraded",
                "detail": "high_latency",
                "category": "transport",
                "issue_code": "UPSTREAM_HIGH_LATENCY",
            }
        ],
    }
]

__all__ = [
    "DECLARED_DEPENDENCY_EXAMPLES",
    "PRODUCT_TRUST_TELEMETRY_SEED_EXAMPLES",
    "TRUST_TELEMETRY_SUMMARY_EXAMPLE",
]
