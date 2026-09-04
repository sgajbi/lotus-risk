from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.attribution_examples import HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE
from app.contracts.attribution_inputs import AttributionInputMode
from app.contracts.attribution_metadata_outputs import HistoricalAttributionMetadata
from app.contracts.attribution_result_outputs import HistoricalAttributionPeriodResult
from app.contracts.risk import RiskRequestScope


class HistoricalAttributionResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this attribution response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: AttributionInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateless"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for attribution calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, HistoricalAttributionPeriodResult] = Field(
        description="Period-level attribution results keyed by period name.",
        json_schema_extra={
            "example": {
                "YTD": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-28",
                    "attribution_sets": [],
                    "error": None,
                }
            }
        },
    )
    metadata: HistoricalAttributionMetadata = Field(
        description="Historical attribution contract and methodology metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "historical_attribution.v1",
                "covariance_method": "EMPIRICAL",
                "annualization_basis": 252,
                "metric_unit_semantics": {
                    "VOLATILITY": "decimal_ratio",
                    "TRACKING_ERROR": "decimal_ratio",
                },
                "requested_attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
                "requested_metrics": ["VOLATILITY", "TRACKING_ERROR"],
                "requested_grouping_dimensions": ["SECTOR"],
                "min_observations_policy": "STRICT",
                "stateful_active_risk_supported_grouping_dimensions": [
                    "POSITION",
                    "SECTOR",
                    "ASSET_CLASS",
                    "ISSUER",
                ],
                "stateful_active_risk_gated_grouping_dimensions": [],
                "stateful_active_risk_gate_reason": "none",
            }
        },
    )
    model_config = ConfigDict(
        json_schema_extra={"example": cast(Any, HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE)}
    )


__all__ = ["HistoricalAttributionResponse"]
