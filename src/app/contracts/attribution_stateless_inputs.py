from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.contracts.attribution_common_inputs import (
    AttributionOptions,
    ExposurePoint,
    requires_active_attribution,
    validate_unique_period_names,
)
from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope


def validate_active_attribution_inputs(
    *,
    attribution_options: AttributionOptions,
    benchmark_returns: list[ReturnPoint],
    benchmark_exposure_history: list[ExposurePoint],
) -> None:
    if not requires_active_attribution(attribution_options):
        return
    if not benchmark_returns:
        raise ValueError(
            "benchmark_returns are required when requesting ACTIVE_RISK or TRACKING_ERROR attribution"
        )
    if not benchmark_exposure_history:
        raise ValueError(
            "benchmark_exposure_history are required when requesting ACTIVE_RISK or TRACKING_ERROR attribution"
        )


class HistoricalAttributionStatelessInput(BaseModel):
    scope: RiskRequestScope = Field(
        description="Scope and policy context for historical attribution calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    periods: list[RiskRequestPeriod] = Field(
        description="List of periods to evaluate historical attribution.",
        json_schema_extra={"example": [{"type": "YTD", "name": "YTD"}]},
    )
    returns: list[ReturnPoint] = Field(
        description="Portfolio return observations in percentage points.",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.62}]},
    )
    benchmark_returns: list[ReturnPoint] = Field(
        default_factory=list,
        description="Benchmark return observations in percentage points (required for active attribution).",
        json_schema_extra={"example": [{"date": "2026-01-02", "value": 0.51}]},
    )
    exposure_history: list[ExposurePoint] = Field(
        description="Portfolio exposure history grouped by requested dimensions.",
        json_schema_extra={
            "example": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.245,
                }
            ]
        },
    )
    benchmark_exposure_history: list[ExposurePoint] = Field(
        default_factory=list,
        description="Benchmark exposure history for active-risk attribution decomposition.",
        json_schema_extra={
            "example": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.210,
                }
            ]
        },
    )
    attribution_options: AttributionOptions = Field(
        default_factory=AttributionOptions,
        description="Historical attribution calculation options.",
        json_schema_extra={
            "example": {
                "attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
                "metrics": ["VOLATILITY", "TRACKING_ERROR"],
                "grouping_dimensions": ["POSITION", "SECTOR"],
                "annualization_basis": 252,
                "covariance_method": "EMPIRICAL",
                "min_observations_policy": "STRICT",
            }
        },
    )

    @model_validator(mode="after")
    def validate_semantics(self) -> "HistoricalAttributionStatelessInput":
        validate_unique_period_names(self.periods)
        validate_active_attribution_inputs(
            attribution_options=self.attribution_options,
            benchmark_returns=self.benchmark_returns,
            benchmark_exposure_history=self.benchmark_exposure_history,
        )
        return self


__all__ = [
    "HistoricalAttributionStatelessInput",
    "validate_active_attribution_inputs",
]
