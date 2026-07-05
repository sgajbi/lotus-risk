from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.concentration_common_inputs import (
    ConcentrationInputMode,
    EnrichmentPolicy,
    IssuerGroupingLevel,
)
from app.contracts.concentration_examples import CONCENTRATION_REQUEST_EXAMPLES
from app.contracts.concentration_simulation_inputs import SimulationConcentrationInput
from app.contracts.concentration_stateful_inputs import StatefulConcentrationInput
from app.contracts.concentration_stateless_inputs import StatelessConcentrationInput


class ConcentrationRequest(BaseModel):
    input_mode: ConcentrationInputMode = Field(
        default=ConcentrationInputMode.STATELESS,
        description="Execution mode for concentration analytics: stateless, stateful, or simulation.",
        json_schema_extra={"example": "simulation"},
    )
    stateless_input: StatelessConcentrationInput | None = Field(
        default=None,
        description="Stateless execution payload with fully supplied positions.",
        json_schema_extra={
            "example": {
                "current_positions": [{"security_id": "AAPL.US", "quantity": 1000.0}],
                "projected_positions": [{"security_id": "AAPL.US", "proposed_quantity": 1200.0}],
                "top_n": 10,
            }
        },
    )
    stateful_input: StatefulConcentrationInput | None = Field(
        default=None,
        description="Stateful execution payload with identifiers resolved through lotus-core.",
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "reporting_currency": "USD",
                "include_cash_positions": True,
                "include_zero_quantity_positions": False,
                "top_n": 10,
            }
        },
    )
    simulation_input: SimulationConcentrationInput | None = Field(
        default=None,
        description="Simulation execution payload orchestrated through lotus-core simulation session APIs.",
        json_schema_extra={
            "example": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "session_id": "SIM_0001",
                "expected_version": 3,
                "simulation_changes": [
                    {"security_id": "SEC_AAPL_US", "transaction_type": "BUY", "quantity": 20.0}
                ],
                "top_n": 10,
            }
        },
    )
    issuer_grouping_level: IssuerGroupingLevel = Field(
        default=IssuerGroupingLevel.ULTIMATE_PARENT,
        description="Issuer grouping hierarchy used for issuer concentration analytics.",
        json_schema_extra={"example": "ultimate_parent"},
    )
    enrichment_policy: EnrichmentPolicy = Field(
        default=EnrichmentPolicy.MERGE_CALLER_THEN_CORE,
        description=(
            "Controls issuer enrichment precedence between caller-provided issuer mappings and lotus-core enrichment."
        ),
        json_schema_extra={"example": "merge_caller_then_core"},
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": cast(Any, CONCENTRATION_REQUEST_EXAMPLES)},
    )

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "ConcentrationRequest":
        if self.input_mode == ConcentrationInputMode.STATELESS and self.stateless_input is None:
            self.stateless_input = StatelessConcentrationInput()

        if self.input_mode == ConcentrationInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")

        if self.input_mode == ConcentrationInputMode.SIMULATION and self.simulation_input is None:
            raise ValueError("simulation_input is required when input_mode=simulation")

        return self


__all__ = ["ConcentrationRequest"]
