from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.contracts.concentration_stateful_inputs import StatefulConcentrationInput


class SimulationChangeInput(BaseModel):
    security_id: str = Field(
        description="Canonical security identifier targeted by the simulated transaction.",
        json_schema_extra={"example": "SEC_AAPL_US"},
    )
    transaction_type: str = Field(
        description="Simulation transaction type (for example BUY or SELL).",
        json_schema_extra={"example": "BUY"},
    )
    quantity: float | None = Field(
        default=None,
        description="Optional quantity magnitude for the simulation change.",
        json_schema_extra={"example": 20.0},
    )
    price: float | None = Field(  # monetary-float-allow: existing lotus-core simulation DTO.
        default=None,
        description="Optional transaction price used by lotus-core simulation change model.",
        json_schema_extra={"example": 195.05},
    )
    amount: float | None = Field(  # monetary-float-allow: existing lotus-core simulation DTO.
        default=None,
        description="Optional transaction amount used by lotus-core simulation change model.",
        json_schema_extra={"example": 3901.0},
    )
    currency: str | None = Field(
        default=None,
        description="Optional ISO currency code for amount/price context.",
        json_schema_extra={"example": "USD"},
    )
    effective_date: date | None = Field(
        default=None,
        description="Optional effective date for this simulation change.",
        json_schema_extra={"example": "2026-02-27"},
    )
    metadata: dict[str, object] | None = Field(
        default=None,
        description="Optional opaque metadata forwarded to lotus-core simulation changes.",
        json_schema_extra={"example": {"note": "rebalance adjustment"}},
    )


class SimulationConcentrationInput(StatefulConcentrationInput):
    simulation_changes: list[SimulationChangeInput] = Field(
        description="Simulation changes applied to lotus-core simulation session before snapshot pull.",
        json_schema_extra={"example": [{"security_id": "SEC_AAPL_US", "transaction_type": "BUY"}]},
    )
    session_id: str | None = Field(
        default=None,
        description="Optional existing simulation session identifier for iterative workflows.",
        json_schema_extra={"example": "SIM_0001"},
    )
    start_new_session: bool = Field(
        default=False,
        description="When true, forces lotus-risk to create a new lotus-core simulation session.",
        json_schema_extra={"example": False},
    )
    session_ttl_hours: int | None = Field(
        default=None,
        ge=1,
        le=168,
        description=(
            "Optional simulation session TTL in hours when creating a new session. "
            "Must be within lotus-core policy bounds (1..168)."
        ),
        json_schema_extra={"example": 24},
    )
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description="Optional optimistic lock version forwarded to lotus-core snapshot simulation block.",
        json_schema_extra={"example": 3},
    )

    @model_validator(mode="after")
    def validate_session_controls(self) -> "SimulationConcentrationInput":
        if self.session_id and not self.start_new_session and self.session_ttl_hours is not None:
            raise ValueError(
                "simulation_input.session_ttl_hours is not allowed when reusing simulation_input.session_id"
            )
        return self


__all__ = [
    "SimulationChangeInput",
    "SimulationConcentrationInput",
]
