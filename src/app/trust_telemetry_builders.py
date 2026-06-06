from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI

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
from app.trust_telemetry_models import (
    DeclaredConsumerDependencyTelemetry,
    DeclaredProductTrustTelemetrySnapshot,
    DependencyTelemetrySignal,
    ProductTrustTelemetrySeed,
    TrustTelemetryReviewSummary,
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dependency_telemetry_signals(
    dependencies: list[DependencyRuntimeView],
) -> list[DependencyTelemetrySignal]:
    return [
        DependencyTelemetrySignal(
            service=dependency.service,
            status=dependency.status,
            detail=dependency.detail,
            category=dependency.category,
            issue_code=dependency.issue_code,
        )
        for dependency in dependencies
    ]


def _source_services_from_metadata(metadata: AuditMetadataFields | None) -> list[str]:
    return list(metadata.source_services) if metadata is not None else []


def _upstream_fingerprints_from_metadata(metadata: AuditMetadataFields | None) -> dict[str, str]:
    return dict(metadata.upstream_request_fingerprints) if metadata is not None else {}


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
        source_services=_source_services_from_metadata(metadata),
        upstream_request_fingerprints=_upstream_fingerprints_from_metadata(metadata),
        dependency_signals=_dependency_telemetry_signals(dependencies),
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
