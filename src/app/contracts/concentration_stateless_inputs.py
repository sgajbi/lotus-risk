from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.contracts.concentration_common_inputs import CurrentPosition, ProjectedPosition


class StatelessExposureBasis(str, Enum):
    MARKET_VALUE_BASE = "market_value_base"
    QUANTITY_PROXY = "quantity_proxy"


def _state_exposure_basis(
    *,
    positions: list[CurrentPosition] | list[ProjectedPosition],
    market_value_field: str,
    quantity_field: str,
    state_name: str,
) -> StatelessExposureBasis | None:
    if not positions:
        return None

    has_market_values = [
        getattr(position, market_value_field) is not None for position in positions
    ]
    if any(has_market_values):
        if not all(has_market_values):
            raise ValueError(
                f"{state_name} positions cannot mix market-value and quantity exposure bases"
            )
        return StatelessExposureBasis.MARKET_VALUE_BASE

    has_quantities = [getattr(position, quantity_field) is not None for position in positions]
    if not all(has_quantities):
        raise ValueError(
            f"{state_name} positions require every row to provide market value or quantity"
        )
    return StatelessExposureBasis.QUANTITY_PROXY


def stateless_exposure_basis(
    payload: StatelessConcentrationInput,
) -> StatelessExposureBasis | None:
    current_basis = _state_exposure_basis(
        positions=payload.current_positions,
        market_value_field="market_value_base",
        quantity_field="quantity",
        state_name="current",
    )
    projected_basis = _state_exposure_basis(
        positions=payload.projected_positions,
        market_value_field="projected_market_value_base",
        quantity_field="proposed_quantity",
        state_name="projected",
    )
    if current_basis and projected_basis and current_basis != projected_basis:
        raise ValueError("current and projected positions must use the same exposure basis")
    return current_basis or projected_basis


class StatelessConcentrationInput(BaseModel):
    current_positions: list[CurrentPosition] = Field(
        default_factory=list,
        description="Current portfolio positions used to compute baseline concentration.",
        json_schema_extra={"example": [{"security_id": "AAPL.US", "quantity": 1000.0}]},
    )
    projected_positions: list[ProjectedPosition] = Field(
        default_factory=list,
        description="Projected positions used to compute post-change concentration.",
        json_schema_extra={"example": [{"security_id": "AAPL.US", "proposed_quantity": 1200.0}]},
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Top-N bucket used for single-position concentration aggregates.",
        json_schema_extra={"example": 10},
    )

    @model_validator(mode="after")
    def validate_exposure_basis(self) -> StatelessConcentrationInput:
        stateless_exposure_basis(self)
        return self


__all__ = [
    "StatelessConcentrationInput",
    "StatelessExposureBasis",
    "stateless_exposure_basis",
]
