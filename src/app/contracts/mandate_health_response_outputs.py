from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.mandate_health_common import MandateRiskHealthState
from app.contracts.mandate_health_metric_outputs import (
    MandateRiskHealthMethodologyPosture,
    MandateRiskHealthSourceMetric,
)


class MandateRiskHealthContextResponse(BaseModel):
    product_name: Literal["MandateRiskHealthContext"] = Field(
        default="MandateRiskHealthContext",
        description="Source-owned product emitted by lotus-risk for mandate health risk context.",
        json_schema_extra={"example": "MandateRiskHealthContext"},
    )
    product_version: Literal["v1"] = Field(
        default="v1",
        description="Product contract version.",
        json_schema_extra={"example": "v1"},
    )
    lineage_version: Literal["mandate-risk-health-context.v1"] = Field(
        default="mandate-risk-health-context.v1",
        description="Lineage policy version used for this source product.",
        json_schema_extra={"example": "mandate-risk-health-context.v1"},
    )
    source_services: list[str] = Field(
        default_factory=lambda: ["lotus-risk"],
        description="Services whose data or calculations contributed to this response.",
        json_schema_extra={"example": ["lotus-risk"]},
    )
    upstream_request_fingerprints: dict[str, str] = Field(
        default_factory=dict,
        description="Upstream request fingerprints directly used by this source product.",
        json_schema_extra={"example": {}},
    )
    benchmark_context: dict[str, object] = Field(
        default_factory=dict,
        description="Benchmark context used for the source-owned tracking-error evaluation.",
        json_schema_extra={"example": {"requested": True, "reason": "APPLIED"}},
    )
    correlation_id: str | None = Field(
        default=None,
        description="Request correlation identifier when available from the request context.",
        json_schema_extra={"example": "corr-123"},
    )
    portfolio_id: str = Field(
        description="Portfolio identifier evaluated by the source product.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    as_of_date: dt.date = Field(
        description="As-of date for the source-owned mandate health risk context.",
        json_schema_extra={"example": "2026-02-27"},
    )
    period_name: str = Field(
        description="Resolved period key evaluated by the source product.",
        json_schema_extra={"example": "YTD"},
    )
    health_state: MandateRiskHealthState = Field(
        description="Bounded risk health posture derived from source-owned tracking error.",
        json_schema_extra={"example": "attention"},
    )
    threshold_breached: bool | None = Field(
        default=None,
        description="Whether source-owned tracking error breached the supplied attention threshold.",
        json_schema_extra={"example": True},
    )
    tracking_error_attention_threshold: Decimal = Field(
        description="Applied annualized tracking-error threshold as a decimal ratio.",
        json_schema_extra={"example": "0.05"},
    )
    source_metric: MandateRiskHealthSourceMetric = Field(
        description="Bounded source metric evidence used to derive health state.",
        json_schema_extra={
            "example": {
                "metric_name": "TRACKING_ERROR",
                "annualized_tracking_error": "0.0425",
                "aligned_observation_count": 64,
            }
        },
    )
    methodology_posture: MandateRiskHealthMethodologyPosture = Field(
        default_factory=MandateRiskHealthMethodologyPosture,
        description="Source ownership and methodology posture for consumers.",
        json_schema_extra={
            "example": {
                "source_product_name": "MandateRiskHealthContext",
                "source_product_version": "v1",
                "source_service": "lotus-risk",
                "source_metrics_product": "RiskMetricsReport:v1",
                "methodology_version": "risk.v1",
                "source_route": "/analytics/risk/calculate",
            }
        },
    )
    request_fingerprint: str = Field(
        description="Fingerprint of the mandate health context request.",
        json_schema_extra={"example": "sha256:..."},
    )
    source_request_fingerprint: str = Field(
        description="Fingerprint of the underlying RiskMetricsReport request.",
        json_schema_extra={"example": "sha256:..."},
    )
    reason_codes: list[str] = Field(
        description="Bounded reason codes safe for downstream supportability and audit use.",
        json_schema_extra={
            "example": [
                "MANDATE_RISK_HEALTH_TRACKING_ERROR_SOURCE_READY",
                "RISK_METHODOLOGY_SOURCE_OWNED",
            ]
        },
    )
