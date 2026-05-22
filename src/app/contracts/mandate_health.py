from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


MandateRiskHealthState = Literal["ready", "attention", "unavailable"]


class MandateRiskHealthContextRequest(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier for the mandate health risk context.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    scope: RiskRequestScope = Field(
        description="Risk scope and as-of date used for source-owned mandate health evaluation.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-27",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    period: RiskRequestPeriod = Field(
        description="Single risk period evaluated for mandate health context.",
        json_schema_extra={"example": {"type": "YTD", "name": "YTD"}},
    )
    portfolio_open_date: dt.date = Field(
        description="Portfolio inception date used for SI period handling.",
        json_schema_extra={"example": "2024-01-01"},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.25}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        description="Benchmark return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.18}]},
    )
    tracking_error_attention_threshold: Decimal = Field(
        default=Decimal("0.05"),
        ge=Decimal("0"),
        description=(
            "Annualized tracking-error attention threshold as a decimal ratio. "
            "For example, 0.05 represents 5 percent annualized tracking error."
        ),
        json_schema_extra={"example": "0.05"},
    )

    model_config = ConfigDict(extra="forbid")


class MandateRiskHealthSourceMetric(BaseModel):
    metric_name: Literal["TRACKING_ERROR"] = Field(
        default="TRACKING_ERROR",
        description="Source-owned risk metric used for mandate health posture.",
        json_schema_extra={"example": "TRACKING_ERROR"},
    )
    annualized_tracking_error: Decimal | None = Field(
        default=None,
        description="Annualized tracking error as a decimal ratio when source-ready.",
        json_schema_extra={"example": "0.0425"},
    )
    aligned_observation_count: int = Field(
        default=0,
        ge=0,
        description="Aligned portfolio and benchmark observations used by the source metric.",
        json_schema_extra={"example": 64},
    )


class MandateRiskHealthMethodologyPosture(BaseModel):
    source_product_name: Literal["MandateRiskHealthContext"] = Field(
        default="MandateRiskHealthContext",
        description="Source-owned mandate health risk product name.",
        json_schema_extra={"example": "MandateRiskHealthContext"},
    )
    source_product_version: Literal["v1"] = Field(
        default="v1",
        description="Source-owned mandate health risk product version.",
        json_schema_extra={"example": "v1"},
    )
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Authoritative source service for this risk context.",
        json_schema_extra={"example": "lotus-risk"},
    )
    source_metrics_product: Literal["RiskMetricsReport:v1"] = Field(
        default="RiskMetricsReport:v1",
        description="Underlying source-owned risk metrics product used for this context.",
        json_schema_extra={"example": "RiskMetricsReport:v1"},
    )
    methodology_version: Literal["risk.v1"] = Field(
        default="risk.v1",
        description="Risk methodology version used by the source calculation.",
        json_schema_extra={"example": "risk.v1"},
    )
    source_route: Literal["/analytics/risk/calculate"] = Field(
        default="/analytics/risk/calculate",
        description="Underlying source route used for risk metric calculation.",
        json_schema_extra={"example": "/analytics/risk/calculate"},
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
