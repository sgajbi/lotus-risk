from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.concentration_common_inputs import CurrentPosition, ProjectedPosition


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


__all__ = ["StatelessConcentrationInput"]
