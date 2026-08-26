from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.risk import RiskRequestPeriod


class DrawdownInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


class BenchmarkDrawdownPolicy(BaseModel):
    include_benchmark: bool = Field(
        default=False,
        description="Whether benchmark-relative drawdown should be computed.",
        json_schema_extra={"example": False},
    )
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] = Field(
        default="IGNORE",
        description="Behavior when benchmark drawdown is requested but benchmark series is unavailable.",
        json_schema_extra={"example": "IGNORE"},
    )


class DrawdownAnalysisOptions(BaseModel):
    include_underwater_series: bool = Field(
        default=False,
        description="Whether underwater drawdown time series points should be included in responses.",
        json_schema_extra={"example": False},
    )
    include_episode_list: bool = Field(
        default=True,
        description="Whether drawdown episodes should be returned in responses.",
        json_schema_extra={"example": True},
    )
    top_n_episodes: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of worst drawdown episodes to return per period.",
        json_schema_extra={"example": 5},
    )
    cdar_alpha: float = Field(
        default=0.95,
        description="Confidence level used for drawdown-at-risk and conditional drawdown-at-risk metrics.",
        json_schema_extra={"example": 0.95},
    )
    minimum_episode_depth_bps: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum episode depth (in basis points) required to include an episode in the list.",
        json_schema_extra={"example": 25.0},
    )
    duration_unit: Literal["BUSINESS_DAYS", "CALENDAR_DAYS"] = Field(
        default="BUSINESS_DAYS",
        description="Duration convention used for drawdown episode timing metrics.",
        json_schema_extra={"example": "BUSINESS_DAYS"},
    )

    @model_validator(mode="after")
    def validate_alpha(self) -> DrawdownAnalysisOptions:
        allowed = {0.90, 0.95, 0.99}
        if self.cdar_alpha not in allowed:
            raise ValueError("cdar_alpha must be one of 0.90, 0.95, or 0.99")
        return self


def validate_unique_period_names(periods: list[RiskRequestPeriod]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        raise ValueError(
            "Duplicate period names resolved in request: "
            + ", ".join(duplicates)
            + ". Each period name (or type fallback) must be unique."
        )


__all__ = [
    "BenchmarkDrawdownPolicy",
    "DrawdownAnalysisOptions",
    "DrawdownInputMode",
    "validate_unique_period_names",
]
