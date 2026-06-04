from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.contracts.audit import AuditMetadataFields
from app.domain_data_products import (
    REPO_RELATIVE_CONSUMER_DECLARATION_PATH,
    REPO_RELATIVE_PRODUCER_DECLARATION_PATH,
    get_declared_product,
    get_local_consumer_declaration_fingerprint,
    get_local_producer_declaration_fingerprint,
    list_declared_dependencies,
    list_declared_products,
)
from app.ops_runtime import DependencyRuntimeView, resolve_ops_status, resolve_readiness_status

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
                    "request_fingerprint": "sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c",
                    "source_services": ["lotus-risk", "lotus-performance"],
                    "upstream_request_fingerprints": {
                        "lotus-performance:/integration/returns/series": "sha256:8d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a1"
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


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_product_trust_telemetry_seed(
    *,
    app: FastAPI,
    product_name: str,
    product_version: str,
    metadata: AuditMetadataFields | None = None,
) -> ProductTrustTelemetrySeed:
    declared_product = get_declared_product(
        product_name=product_name,
        product_version=product_version,
    )
    _readiness_status_code, readiness_status, dependencies = resolve_readiness_status(app)
    ops_status, _ = resolve_ops_status(app)

    return ProductTrustTelemetrySeed(
        product_name=product_name,
        product_version=product_version,
        authoritative_domain=declared_product["authoritative_domain"],
        product_family=declared_product["product_family"],
        approved_consumers=list(declared_product.get("approved_consumers", [])),
        required_trust_metadata=list(declared_product.get("required_trust_metadata", [])),
        lifecycle_status=declared_product["lifecycle_status"],
        current_routes=list(declared_product.get("current_routes", [])),
        emitted_at=_utc_now(),
        readiness_status=readiness_status,
        ops_status=ops_status,
        draining=bool(getattr(app.state, "is_draining", False)),
        lineage_version=metadata.lineage_version if metadata is not None else None,
        request_fingerprint=metadata.request_fingerprint if metadata is not None else None,
        source_services=list(metadata.source_services) if metadata is not None else [],
        upstream_request_fingerprints=(
            dict(metadata.upstream_request_fingerprints) if metadata is not None else {}
        ),
        dependency_signals=[
            DependencyTelemetrySignal(
                service=dependency.service,
                status=dependency.status,
                detail=dependency.detail,
                category=dependency.category,
                issue_code=dependency.issue_code,
            )
            for dependency in dependencies
        ],
    )


def _dependency_index(
    dependencies: list[DependencyRuntimeView],
) -> dict[str, DependencyRuntimeView]:
    return {dependency.service: dependency for dependency in dependencies}


def _declared_dependency_telemetry(
    *,
    dependency: dict[str, Any],
    dependency_index: dict[str, DependencyRuntimeView],
) -> DeclaredConsumerDependencyTelemetry:
    producer_repository = dependency["producer_repository"]
    runtime_dependency = dependency_index.get(producer_repository)
    return DeclaredConsumerDependencyTelemetry(
        product_name=dependency["product_name"],
        producer_repository=producer_repository,
        required_product_version=dependency["required_product_version"],
        consumption_mode=dependency["consumption_mode"],
        failure_posture=dependency["failure_posture"],
        validation_lanes=list(dependency.get("validation_lanes", [])),
        required_trust_metadata=list(dependency.get("required_trust_metadata", [])),
        runtime_status=runtime_dependency.status if runtime_dependency is not None else None,
        runtime_detail=runtime_dependency.detail if runtime_dependency is not None else None,
        runtime_category=runtime_dependency.category if runtime_dependency is not None else None,
        runtime_issue_code=(
            runtime_dependency.issue_code if runtime_dependency is not None else None
        ),
    )


def _declared_dependency_telemetry_list(
    dependency_index: dict[str, DependencyRuntimeView],
) -> list[DeclaredConsumerDependencyTelemetry]:
    return [
        _declared_dependency_telemetry(
            dependency=dependency,
            dependency_index=dependency_index,
        )
        for dependency in list_declared_dependencies()
    ]


def _declared_product_seeds(app: FastAPI) -> list[ProductTrustTelemetrySeed]:
    return [
        build_product_trust_telemetry_seed(
            app=app,
            product_name=product["product_name"],
            product_version=product["product_version"],
        )
        for product in list_declared_products()
    ]


def _trust_telemetry_summary(
    *,
    products: list[ProductTrustTelemetrySeed],
    declared_dependencies: list[DeclaredConsumerDependencyTelemetry],
) -> TrustTelemetryReviewSummary:
    degraded_dependency_products = [
        dependency.product_name
        for dependency in declared_dependencies
        if dependency.runtime_status == "degraded"
    ]
    unavailable_dependency_products = [
        dependency.product_name
        for dependency in declared_dependencies
        if dependency.runtime_status == "unavailable"
    ]
    missing_runtime_services = sorted(
        {
            dependency.producer_repository
            for dependency in declared_dependencies
            if dependency.runtime_status is None
        }
    )
    return TrustTelemetryReviewSummary(
        declared_product_count=len(products),
        declared_dependency_count=len(declared_dependencies),
        degraded_dependency_count=len(degraded_dependency_products),
        unavailable_dependency_count=len(unavailable_dependency_products),
        missing_runtime_service_count=len(missing_runtime_services),
        degraded_dependency_products=degraded_dependency_products,
        unavailable_dependency_products=unavailable_dependency_products,
        missing_runtime_services=missing_runtime_services,
    )


def build_declared_product_trust_telemetry_snapshot(
    *,
    app: FastAPI,
    service_name: str,
) -> DeclaredProductTrustTelemetrySnapshot:
    _readiness_status_code, _readiness_status, dependencies = resolve_readiness_status(app)
    declared_dependencies = _declared_dependency_telemetry_list(
        dependency_index=_dependency_index(dependencies),
    )
    products = _declared_product_seeds(app)

    return DeclaredProductTrustTelemetrySnapshot(
        service=service_name,
        declaration_source=REPO_RELATIVE_PRODUCER_DECLARATION_PATH.as_posix(),
        declaration_fingerprint=get_local_producer_declaration_fingerprint(),
        consumer_declaration_source=REPO_RELATIVE_CONSUMER_DECLARATION_PATH.as_posix(),
        consumer_declaration_fingerprint=get_local_consumer_declaration_fingerprint(),
        declared_dependencies=declared_dependencies,
        summary=_trust_telemetry_summary(
            products=products,
            declared_dependencies=declared_dependencies,
        ),
        products=products,
    )
