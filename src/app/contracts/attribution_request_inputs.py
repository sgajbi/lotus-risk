from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.attribution_common_inputs import AttributionInputMode
from app.contracts.attribution_examples import HISTORICAL_ATTRIBUTION_REQUEST_EXAMPLE
from app.contracts.attribution_stateful_inputs import HistoricalAttributionStatefulInput
from app.contracts.attribution_stateless_inputs import HistoricalAttributionStatelessInput


class HistoricalAttributionRequest(BaseModel):
    input_mode: AttributionInputMode = Field(
        default=AttributionInputMode.STATELESS,
        description="Execution mode for historical attribution analytics.",
        json_schema_extra={"example": "stateless"},
    )
    stateless_input: HistoricalAttributionStatelessInput | None = Field(
        default=None,
        description="Stateless payload with fully supplied returns and exposure history.",
        json_schema_extra={
            "example": {
                "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
                "periods": [{"type": "YTD", "name": "YTD"}],
                "returns": [{"date": "2026-01-02", "value": 0.62}],
                "exposure_history": [
                    {
                        "date": "2026-01-02",
                        "grouping_dimension": "SECTOR",
                        "group_key": "SECTOR_TECH",
                        "weight": 0.245,
                    }
                ],
            }
        },
    )
    stateful_input: HistoricalAttributionStatefulInput | None = Field(
        default=None,
        description=(
            "Stateful payload for returns/exposure sourcing through lotus-performance and lotus-core. "
            "Stateful ACTIVE_RISK currently supports POSITION, SECTOR, ASSET_CLASS, and ISSUER; "
            "ISSUER is supported through lotus-performance benchmark exposure context issuer groups. "
            "CUSTOM grouping is not supported in stateful mode."
        ),
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "attribution_options": {
                    "attribution_types": ["ACTIVE_RISK"],
                    "metrics": ["TRACKING_ERROR"],
                    "grouping_dimensions": ["SECTOR"],
                    "annualization_basis": 252,
                    "covariance_method": "EMPIRICAL",
                    "min_observations_policy": "STRICT",
                },
            }
        },
    )
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": cast(Any, HISTORICAL_ATTRIBUTION_REQUEST_EXAMPLE)},
    )

    @model_validator(mode="after")
    def normalize_and_validate(self) -> HistoricalAttributionRequest:
        if self.input_mode == AttributionInputMode.STATELESS and self.stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")
        if self.input_mode == AttributionInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")
        return self


__all__ = ["HistoricalAttributionRequest"]
