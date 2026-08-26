from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

RiskMetric = Literal[
    "VOLATILITY",
    "DRAWDOWN",
    "SHARPE",
    "SORTINO",
    "BETA",
    "TRACKING_ERROR",
    "INFORMATION_RATIO",
    "VAR",
]
RiskSupportabilityState = Literal[
    "ready",
    "stale",
    "degraded",
    "empty",
    "error",
    "permission_blocked",
    "unsupported",
]
RiskSupportabilityReason = Literal[
    "calculation_complete",
    "benchmark_unavailable",
    "calculation_quality_issue",
    "insufficient_aligned_observations",
    "insufficient_observations",
    "no_return_observations",
    "permission_blocked",
    "stale_source_observations",
    "unsupported_input_mode",
]
RiskFreshnessBucket = Literal["current", "same_day", "stale", "unknown"]


class RiskInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"


class RiskRequestScope(BaseModel):
    as_of_date: dt.date = Field(
        default_factory=dt.date.today,
        description="As-of date used for risk metric evaluation.",
        json_schema_extra={"example": "2025-03-31"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency for normalized outputs.",
        json_schema_extra={"example": "USD"},
    )
    net_or_gross: Literal["NET", "GROSS"] = Field(
        default="NET",
        description="Whether returns represent net or gross performance.",
        json_schema_extra={"example": "NET"},
    )


class RiskRequestPeriod(BaseModel):
    PERIOD_ALIASES: ClassVar[dict[str, str]] = {
        "ONE_YEAR": "1Y",
        "THREE_YEAR": "3Y",
        "FIVE_YEAR": "5Y",
        "ITD": "SI",
    }

    type: Literal[
        "EXPLICIT",
        "YEAR",
        "MTD",
        "QTD",
        "YTD",
        "1Y",
        "3Y",
        "5Y",
        "ONE_YEAR",
        "THREE_YEAR",
        "FIVE_YEAR",
        "SI",
    ] = Field(
        description=(
            "Period type used for metric aggregation. Prefer canonical values "
            "EXPLICIT, YEAR, MTD, QTD, YTD, 1Y, 3Y, 5Y, and SI. Legacy aliases "
            "ONE_YEAR, THREE_YEAR, FIVE_YEAR, and ITD are accepted and normalized."
        ),
        json_schema_extra={"example": "3Y"},
    )
    name: str | None = Field(
        default=None,
        description="Optional display label for this period.",
        json_schema_extra={"example": "explicit_q1_2025"},
    )
    from_date: dt.date | None = Field(
        default=None,
        description="Explicit period start date (required when type=EXPLICIT).",
        json_schema_extra={"example": "2025-01-01"},
    )
    to_date: dt.date | None = Field(
        default=None,
        description="Explicit period end date (required when type=EXPLICIT).",
        json_schema_extra={"example": "2025-03-31"},
    )
    year: int | None = Field(
        default=None,
        description="Calendar year (required when type=YEAR).",
        json_schema_extra={"example": 2025},
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_period_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            period_type = data.get("type")
            if isinstance(period_type, str):
                normalized_type = cls.PERIOD_ALIASES.get(period_type, period_type)
                if normalized_type != period_type:
                    return {**data, "type": normalized_type}
        return data

    @model_validator(mode="after")
    def validate_semantics(self) -> RiskRequestPeriod:
        if self.type == "EXPLICIT" and (self.from_date is None or self.to_date is None):
            raise ValueError("EXPLICIT period requires from/to dates")
        if self.type == "YEAR" and self.year is None:
            raise ValueError("YEAR period requires year")
        return self


class ReturnPoint(BaseModel):
    date: dt.date = Field(
        description="Date of return observation.",
        json_schema_extra={"example": "2025-01-02"},
    )
    value: float = (  # monetary-float-allow: return observation in percentage points, not money.
        Field(
            description="Return value in percentage points.",
            json_schema_extra={"example": 0.85},
        )
    )


def validate_unique_period_names(periods: list[RiskRequestPeriod]) -> None:
    resolved_names = [period.name or period.type for period in periods]
    duplicates = sorted({name for name in resolved_names if resolved_names.count(name) > 1})
    if duplicates:
        duplicate_names = ", ".join(duplicates)
        raise ValueError(
            f"Duplicate period names resolved in request: {duplicate_names}. "
            "Each period name (or type fallback) must be unique."
        )


__all__ = [
    "ReturnPoint",
    "RiskFreshnessBucket",
    "RiskInputMode",
    "RiskMetric",
    "RiskRequestPeriod",
    "RiskRequestScope",
    "RiskSupportabilityReason",
    "RiskSupportabilityState",
    "validate_unique_period_names",
]
