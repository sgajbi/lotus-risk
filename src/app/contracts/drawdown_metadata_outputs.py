from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.risk import RiskCalculationSupportability


class DrawdownMetadata(AuditMetadataFields):
    product_name: Literal["DrawdownAnalyticsReport"] = Field(
        default="DrawdownAnalyticsReport",
        description="Source-owned domain data product emitted by this response.",
        json_schema_extra={"example": "DrawdownAnalyticsReport"},
    )
    product_version: Literal["v1"] = Field(
        default="v1",
        description="Source-owned domain data product version.",
        json_schema_extra={"example": "v1"},
    )
    contract_version: str = Field(
        default="v1",
        description="Drawdown analytics contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="drawdown.v1",
        description="Methodology version used for drawdown analytics formulas.",
        json_schema_extra={"example": "drawdown.v1"},
    )
    include_underwater_series: bool = Field(
        default=False,
        description="Whether underwater drawdown series was included in period results.",
        json_schema_extra={"example": False},
    )
    include_episode_list: bool = Field(
        default=True,
        description="Whether drawdown episode lists were included in period results.",
        json_schema_extra={"example": True},
    )
    top_n_episodes: int = Field(
        default=5,
        description="Maximum number of worst drawdown episodes retained per period.",
        json_schema_extra={"example": 5},
    )
    cdar_alpha: float = Field(
        default=0.95,
        description="Confidence level used for drawdown-at-risk and conditional drawdown-at-risk.",
        json_schema_extra={"example": 0.95},
    )
    minimum_episode_depth_bps: float = Field(
        default=0.0,
        description="Minimum episode depth threshold, in basis points, applied to episode lists.",
        json_schema_extra={"example": 25.0},
    )
    duration_unit: Literal["BUSINESS_DAYS", "CALENDAR_DAYS"] = Field(
        default="BUSINESS_DAYS",
        description="Duration convention applied to episode timing fields.",
        json_schema_extra={"example": "BUSINESS_DAYS"},
    )
    include_benchmark: bool | None = Field(
        default=None,
        description="Whether benchmark-relative drawdown was requested.",
        json_schema_extra={"example": True},
    )
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] | None = Field(
        default=None,
        description="Behavior requested when benchmark series is unavailable.",
        json_schema_extra={"example": "IGNORE"},
    )
    benchmark_context: dict[str, object] = Field(
        default_factory=dict,
        description="Source-owned benchmark context summary for domain-data-product trust metadata.",
        json_schema_extra={"example": {"requested": True, "policy": "IGNORE", "reason": "APPLIED"}},
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={
            "example": {
                "state": "ready",
                "reason": "calculation_complete",
                "freshness_bucket": "current",
                "degraded_metric_count": 0,
                "empty_period_count": 0,
                "evaluated_period_count": 1,
            }
        },
    )


__all__ = ["DrawdownMetadata"]
