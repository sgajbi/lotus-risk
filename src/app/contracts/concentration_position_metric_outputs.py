from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.concentration_metric_field_examples import (
    TOP_POSITION_CURRENT_EXAMPLE,
    TOP_POSITION_PROPOSED_EXAMPLE,
)


class ConcentrationRiskProxy(BaseModel):
    hhi_current: float = Field(
        description=(
            "Current position-level Herfindahl-Hirschman Index on the conventional 0..10000 "
            "scale, computed from positive extracted current position values."
        ),
        json_schema_extra={"example": 2450.0},
    )
    hhi_proposed: float = Field(
        description=(
            "Proposed position-level Herfindahl-Hirschman Index on the conventional 0..10000 "
            "scale after projected positions are applied. Stateless and stateful requests fall "
            "back to current HHI when no proposed position values are available; simulation "
            "requests treat an explicit empty projected book as zero proposed concentration."
        ),
        json_schema_extra={"example": 2710.0},
    )
    hhi_delta: float = Field(
        description="Proposed-minus-current position-level HHI change on the 0..10000 scale.",
        json_schema_extra={"example": 260.0},
    )


class TopPositionDriver(BaseModel):
    security_id: str | None = Field(
        default=None,
        description="Security identifier of the top concentration-driving position.",
        json_schema_extra={"example": "FO_FUND_PIMCO_INC"},
    )
    security_name: str | None = Field(
        default=None,
        description="Display name of the top concentration-driving position when available.",
        json_schema_extra={"example": "PIMCO GIS Income Fund"},
    )
    weight: float = Field(
        description="Portfolio weight of the top concentration-driving position.",
        json_schema_extra={"example": 0.23014},
    )


class SinglePositionConcentration(BaseModel):
    top_position_weight_current: float = Field(
        description=(
            "Highest single-position weight in the baseline state, computed from positive "
            "extracted position values as a decimal ratio in the 0..1 range."
        ),
        json_schema_extra={"example": 0.1245},
    )
    top_position_weight_proposed: float = Field(
        description=(
            "Highest single-position weight in the proposed state as a decimal ratio in the 0..1 "
            "range. Stateless and stateful requests fall back to the baseline top-position "
            "weight when no proposed values are available; simulation requests treat an explicit "
            "empty projected book as zero proposed concentration."
        ),
        json_schema_extra={"example": 0.142},
    )
    top_position_weight_delta: float = Field(
        description="Proposed-minus-baseline top-position weight change as a decimal ratio.",
        json_schema_extra={"example": 0.0175},
    )
    top_n_cumulative_weight_current: float = Field(
        description=(
            "Cumulative baseline weight of the largest N positive extracted position values as "
            "a decimal ratio in the 0..1 range."
        ),
        json_schema_extra={"example": 0.4123},
    )
    top_n_cumulative_weight_proposed: float = Field(
        description=(
            "Cumulative proposed weight of the largest N positive extracted position values as "
            "a decimal ratio in the 0..1 range. Stateless and stateful requests fall back to "
            "the baseline top-N cumulative weight when no proposed values are available; "
            "simulation requests treat an explicit empty projected book as zero proposed "
            "concentration."
        ),
        json_schema_extra={"example": 0.4551},
    )
    top_n_cumulative_weight_delta: float = Field(
        description="Proposed-minus-baseline top-N cumulative weight change as a decimal ratio.",
        json_schema_extra={"example": 0.0428},
    )
    top_n: int = Field(
        description="Top-N parameter used for cumulative single-position concentration calculations.",
        json_schema_extra={"example": 10},
    )
    top_position_current: TopPositionDriver = Field(
        description="Top baseline position driver with identifier and display metadata.",
        json_schema_extra={"example": TOP_POSITION_CURRENT_EXAMPLE},
    )
    top_position_proposed: TopPositionDriver = Field(
        description="Top proposed position driver with identifier and display metadata.",
        json_schema_extra={"example": TOP_POSITION_PROPOSED_EXAMPLE},
    )


__all__ = [
    "ConcentrationRiskProxy",
    "SinglePositionConcentration",
    "TopPositionDriver",
]
