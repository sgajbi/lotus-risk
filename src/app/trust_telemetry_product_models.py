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
