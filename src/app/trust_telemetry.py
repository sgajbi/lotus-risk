from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.contracts.audit import AuditMetadataFields
from app.domain_data_products import (
    REPO_RELATIVE_PRODUCER_DECLARATION_PATH,
    get_declared_product,
    list_declared_products,
)
from app.ops_runtime import resolve_ops_status, resolve_readiness_status

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
    lifecycle_status: TelemetryLifecycleStatus = Field(
        description="Repo-owned lifecycle status mirrored from the governed product declaration.",
        json_schema_extra={"example": "active"},
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
        json_schema_extra={"example": "sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c"},
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
    )


class DeclaredProductTrustTelemetrySnapshot(BaseModel):
    service: str = Field(
        description="Service identifier publishing the local trust telemetry snapshot.",
        json_schema_extra={"example": "lotus-risk"},
    )
    declaration_source: str = Field(
        description="Repo-native producer declaration file used to resolve the declared products.",
        json_schema_extra={
            "example": "contracts/domain-data-products/lotus-risk-products.v1.json"
        },
    )
    products: list[ProductTrustTelemetrySeed] = Field(
        description="Current raw telemetry seeds for each repo-native declared product.",
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
        lifecycle_status=declared_product["lifecycle_status"],
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


def build_declared_product_trust_telemetry_snapshot(
    *,
    app: FastAPI,
    service_name: str,
) -> DeclaredProductTrustTelemetrySnapshot:
    return DeclaredProductTrustTelemetrySnapshot(
        service=service_name,
        declaration_source=REPO_RELATIVE_PRODUCER_DECLARATION_PATH.as_posix(),
        products=[
            build_product_trust_telemetry_seed(
                app=app,
                product_name=product["product_name"],
                product_version=product["product_version"],
            )
            for product in list_declared_products()
        ],
    )
