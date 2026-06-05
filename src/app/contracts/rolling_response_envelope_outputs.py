from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.risk import RiskRequestScope
from app.contracts.rolling_examples import ROLLING_RESPONSE_EXAMPLE
from app.contracts.rolling_inputs import RollingInputMode
from app.contracts.rolling_metadata_outputs import RollingMetadata
from app.contracts.rolling_period_outputs import RollingPeriodResult


class RollingResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this rolling analytics response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: RollingInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateless"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for rolling calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, RollingPeriodResult] = Field(
        description="Rolling metric period results keyed by period name.",
        json_schema_extra={
            "example": {
                "YTD": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-28",
                    "series_count": 41,
                    "benchmark_series_count": 41,
                    "aligned_benchmark_series_count": 41,
                    "window_lengths_requested": [21, 63],
                    "window_count_requested": 2,
                    "window_lengths_emitted": [21, 63],
                    "window_count_emitted": 2,
                    "benchmark_context": {
                        "requested": True,
                        "available": True,
                        "aligned": True,
                        "reason": "APPLIED",
                    },
                    "risk_free_series_count": 41,
                    "aligned_risk_free_series_count": 41,
                    "risk_free_context": {
                        "requested": True,
                        "available": True,
                        "aligned": True,
                        "reason": "APPLIED",
                    },
                    "window_results": [],
                    "quality_flags": [],
                    "error": None,
                }
            }
        },
    )
    metadata: RollingMetadata = Field(
        description="Rolling metric contract and methodology metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "rolling_metrics.v1",
                "annualization_basis": 252,
                "requested_metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                ],
                "window_lengths_requested": [21, 63],
                "window_count_requested": 2,
                "alignment_policy": "INNER_JOIN",
                "min_observations_policy": "STRICT",
                "include_time_series": False,
                "benchmark_context": {
                    "requested": True,
                    "requested_metrics": [
                        "ROLLING_BETA",
                        "ROLLING_TRACKING_ERROR",
                    ],
                },
                "risk_free_context": {
                    "requested": False,
                    "requested_metrics": [],
                },
            }
        },
    )

    model_config = ConfigDict(json_schema_extra={"example": cast(Any, ROLLING_RESPONSE_EXAMPLE)})


__all__ = ["RollingResponse"]
