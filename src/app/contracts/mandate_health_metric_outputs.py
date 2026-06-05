from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


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
