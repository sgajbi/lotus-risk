from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.contracts.concentration_stateful_inputs import StatefulConcentrationInput


class SimulationTransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SimulationChangeInput(BaseModel):
    security_id: str = Field(
        description="Canonical security identifier targeted by the simulated transaction.",
        json_schema_extra={"example": "SEC_AAPL_US"},
    )
    transaction_type: SimulationTransactionType = Field(
        description="Supported simulation transaction type. Supported values: BUY, SELL.",
        json_schema_extra={"example": "BUY"},
    )
    quantity: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Positive quantity magnitude for the simulation change. BUY and SELL changes require "
            "quantity or amount."
        ),
        json_schema_extra={"example": 20.0},
    )
    price: float | None = Field(  # monetary-float-allow: existing lotus-core simulation DTO.
        default=None,
        gt=0,
        description="Optional transaction price used by lotus-core simulation change model.",
        json_schema_extra={"example": 195.05},
    )
    amount: float | None = Field(  # monetary-float-allow: existing lotus-core simulation DTO.
        default=None,
        gt=0,
        description=(
            "Positive transaction amount used by lotus-core simulation change model. BUY and SELL "
            "changes require quantity or amount."
        ),
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

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @model_validator(mode="after")
    def validate_supported_change_semantics(self) -> SimulationChangeInput:
        if self.quantity is None and self.amount is None:
            raise ValueError(
                "simulation_changes[].quantity or simulation_changes[].amount is required for BUY/SELL"
            )
        return self


class SimulationConcentrationInput(StatefulConcentrationInput):
    simulation_changes: list[SimulationChangeInput] = Field(
        description=(
            "BUY/SELL simulation changes applied to the lotus-core simulation session before "
            "snapshot pull. Each change requires a positive quantity or amount."
        ),
        json_schema_extra={
            "example": [{"security_id": "SEC_AAPL_US", "transaction_type": "BUY", "quantity": 20.0}]
        },
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
    def validate_session_controls(self) -> SimulationConcentrationInput:
        if self.session_id and not self.start_new_session and self.session_ttl_hours is not None:
            raise ValueError(
                "simulation_input.session_ttl_hours is not allowed when reusing simulation_input.session_id"
            )
        return self


__all__ = [
    "SimulationChangeInput",
    "SimulationConcentrationInput",
    "SimulationTransactionType",
]
