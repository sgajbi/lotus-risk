from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TelemetryLifecycleStatus = Literal["active", "deprecated", "retired"]


class DependencyTelemetrySignal(BaseModel):
    service: str = Field(
        description="Dependency service identifier contributing runtime trust evidence.",
        json_schema_extra={"example": "lotus-performance"},
    )
    status: str = Field(
        description="Current dependency runtime state observed by lotus-risk.",
        json_schema_extra={"example": "ok"},
    )
    detail: str | None = Field(
        default=None,
        description="Optional operator-facing runtime detail from the dependency view.",
        json_schema_extra={"example": "configured"},
    )
    category: str | None = Field(
        default=None,
        description="Optional structured runtime issue category carried by the dependency view.",
        json_schema_extra={"example": "data_gap"},
    )
    issue_code: str | None = Field(
        default=None,
        description="Optional machine-readable dependency issue code.",
        json_schema_extra={"example": "RISK_FREE_SERIES_EMPTY"},
    )


class ProductTrustTelemetrySeed(BaseModel):
    product_name: str = Field(
        description="Governed product identifier emitted by lotus-risk.",
        json_schema_extra={"example": "RiskMetricsReport"},
    )
    product_version: str = Field(
        description="Governed product version emitted by lotus-risk.",
        json_schema_extra={"example": "v1"},
    )
    authoritative_domain: str = Field(
        description="Authoritative domain declared for the product.",
        json_schema_extra={"example": "risk_analytics"},
    )
    product_family: str = Field(
        description="Declared product family used to classify the product for governance.",
        json_schema_extra={"example": "analytics_output"},
    )
    approved_consumers: list[str] = Field(
        default_factory=list,
        description="Consumers explicitly approved in the repo-native producer declaration.",
        json_schema_extra={"example": ["lotus-gateway"]},
    )
    required_trust_metadata: list[str] = Field(
        default_factory=list,
        description="Trust metadata fields the repo-native declaration requires for the product.",
        json_schema_extra={"example": ["product_name", "product_version", "as_of_date"]},
    )
    lifecycle_status: TelemetryLifecycleStatus = Field(
        description="Repo-owned lifecycle status mirrored from the governed product declaration.",
        json_schema_extra={"example": "active"},
    )
    current_routes: list[str] = Field(
        default_factory=list,
        description="Current API routes declared as publishing or serving this product.",
        json_schema_extra={"example": ["/analytics/risk/calculate"]},
    )
    emitted_at: str = Field(
        description="UTC timestamp when lotus-risk assembled the local trust telemetry seed.",
        json_schema_extra={"example": "2026-04-19T00:00:00Z"},
    )
    readiness_status: str = Field(
        description="Current service readiness posture used as raw input for future certification.",
        json_schema_extra={"example": "ready"},
    )
    ops_status: str = Field(
        description="Current service operations posture used as raw input for future certification.",
        json_schema_extra={"example": "ok"},
    )
    draining: bool = Field(
        description="Whether lotus-risk was draining when the telemetry seed was built.",
        json_schema_extra={"example": False},
    )
    lineage_version: str | None = Field(
        default=None,
        description="Audit lineage schema version carried by the product response when available.",
        json_schema_extra={"example": "risk_audit_lineage.v1"},
    )
    request_fingerprint: str | None = Field(
        default=None,
        description="Current product request fingerprint when response lineage is available.",
        json_schema_extra={
            "example": "sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c"
        },
    )
    source_services: list[str] = Field(
        default_factory=list,
        description="Ordered source-service lineage already published by lotus-risk.",
        json_schema_extra={"example": ["lotus-risk", "lotus-performance"]},
    )
    upstream_request_fingerprints: dict[str, str] = Field(
        default_factory=dict,
        description="Upstream request fingerprints already published by lotus-risk.",
        json_schema_extra={
            "example": {
                "lotus-performance:/integration/returns/series": (
                    "sha256:8d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a1"
                )
            }
        },
    )
    dependency_signals: list[DependencyTelemetrySignal] = Field(
        default_factory=list,
        description="Dependency runtime evidence used as raw trust telemetry input.",
        json_schema_extra={
            "example": [
                {
                    "service": "lotus-performance",
                    "status": "degraded",
                    "detail": "high_latency",
                    "category": "transport",
                    "issue_code": "UPSTREAM_HIGH_LATENCY",
                }
            ]
        },
    )


class DeclaredConsumerDependencyTelemetry(BaseModel):
    product_name: str = Field(
        description="Governed upstream product required by lotus-risk.",
        json_schema_extra={"example": "ReturnsSeriesBundle"},
    )
    producer_repository: str = Field(
        description="Owning repository for the required upstream product.",
        json_schema_extra={"example": "lotus-performance"},
    )
    required_product_version: str = Field(
        description="Governed upstream product version required by lotus-risk.",
        json_schema_extra={"example": "v1"},
    )
    consumption_mode: str = Field(
        description="Declared consumption mode for the upstream dependency.",
        json_schema_extra={"example": "api_read"},
    )
    failure_posture: str = Field(
        description="Declared failure posture when the upstream dependency is unavailable or weak.",
        json_schema_extra={"example": "fail_closed"},
    )
    validation_lanes: list[str] = Field(
        default_factory=list,
        description="Validation lanes in which this dependency is expected to be checked.",
        json_schema_extra={"example": ["feature", "pr-merge"]},
    )
    required_trust_metadata: list[str] = Field(
        default_factory=list,
        description="Trust metadata required from the upstream product declaration.",
        json_schema_extra={"example": ["generated_at", "as_of_date", "correlation_id"]},
    )
    runtime_status: str | None = Field(
        default=None,
        description="Current runtime status observed for the declared upstream producer service.",
        json_schema_extra={"example": "degraded"},
    )
    runtime_detail: str | None = Field(
        default=None,
        description="Current runtime detail observed for the declared upstream producer service.",
        json_schema_extra={"example": "high_latency"},
    )
    runtime_category: str | None = Field(
        default=None,
        description="Current structured runtime issue category for the declared upstream producer service.",
        json_schema_extra={"example": "transport"},
    )
    runtime_issue_code: str | None = Field(
        default=None,
        description="Current machine-readable runtime issue code for the declared upstream producer service.",
        json_schema_extra={"example": "UPSTREAM_HIGH_LATENCY"},
    )


class TrustTelemetryReviewSummary(BaseModel):
    declared_product_count: int = Field(
        description="Number of repo-native declared producer products included in the snapshot.",
        json_schema_extra={"example": 7},
    )
    declared_dependency_count: int = Field(
        description="Number of repo-native declared upstream dependencies included in the snapshot.",
        json_schema_extra={"example": 6},
    )
    degraded_dependency_count: int = Field(
        description="Count of declared upstream dependencies whose producer runtime status is degraded.",
        json_schema_extra={"example": 1},
    )
    unavailable_dependency_count: int = Field(
        description="Count of declared upstream dependencies whose producer runtime status is unavailable.",
        json_schema_extra={"example": 0},
    )
    missing_runtime_service_count: int = Field(
        description="Count of declared upstream dependencies whose producer service has no current runtime view.",
        json_schema_extra={"example": 0},
    )
    degraded_dependency_products: list[str] = Field(
        default_factory=list,
        description="Declared upstream product names currently backed by degraded producer services.",
        json_schema_extra={"example": ["ReturnsSeriesBundle"]},
    )
    unavailable_dependency_products: list[str] = Field(
        default_factory=list,
        description="Declared upstream product names currently backed by unavailable producer services.",
        json_schema_extra={"example": []},
    )
    missing_runtime_services: list[str] = Field(
        default_factory=list,
        description="Declared upstream producer services that currently have no runtime view.",
        json_schema_extra={"example": []},
    )


class DeclaredProductTrustTelemetrySnapshot(BaseModel):
    service: str = Field(
        description="Service identifier publishing the local trust telemetry snapshot.",
        json_schema_extra={"example": "lotus-risk"},
    )
    declaration_source: str = Field(
        description="Repo-native producer declaration file used to resolve the declared products.",
        json_schema_extra={"example": "contracts/domain-data-products/lotus-risk-products.v1.json"},
    )
    declaration_fingerprint: str = Field(
        description="Deterministic fingerprint of the repo-native producer declaration payload.",
        json_schema_extra={
            "example": "sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c"
        },
    )
    consumer_declaration_source: str = Field(
        description="Repo-native consumer declaration file used to resolve declared upstream dependencies.",
        json_schema_extra={
            "example": "contracts/domain-data-products/lotus-risk-consumers.v1.json"
        },
    )
    consumer_declaration_fingerprint: str = Field(
        description="Deterministic fingerprint of the repo-native consumer declaration payload.",
        json_schema_extra={
            "example": "sha256:8d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a1"
        },
    )
    declared_dependencies: list[DeclaredConsumerDependencyTelemetry] = Field(
        description="Current repo-native declared upstream dependencies required by lotus-risk.",
        json_schema_extra={
            "example": [
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
        },
    )
    summary: TrustTelemetryReviewSummary = Field(
        description="Operator-facing rollup of declaration counts and current runtime dependency posture.",
        json_schema_extra={
            "example": {
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
        },
    )
    products: list[ProductTrustTelemetrySeed] = Field(
        description="Current raw telemetry seeds for each repo-native declared product.",
        json_schema_extra={
            "example": [
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
                    "request_fingerprint": (
                        "sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c"
                    ),
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
        },
    )
