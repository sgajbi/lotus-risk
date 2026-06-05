from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.concentration_examples import CONCENTRATION_REQUEST_EXAMPLES


class ConcentrationInputMode(str, Enum):
    STATELESS = "stateless"
    STATEFUL = "stateful"
    SIMULATION = "simulation"


class IssuerGroupingLevel(str, Enum):
    LEGAL_ISSUER = "legal_issuer"
    ULTIMATE_PARENT = "ultimate_parent"


class EnrichmentPolicy(str, Enum):
    USE_CALLER_ONLY = "use_caller_only"
    MERGE_CALLER_THEN_CORE = "merge_caller_then_core"
    CORE_ONLY = "core_only"


class CurrentPosition(BaseModel):
    security_id: str = Field(
        description="Canonical security identifier in the baseline portfolio state.",
        json_schema_extra={"example": "AAPL.US"},
    )
    security_name: str | None = Field(
        default=None,
        description="Optional security display name for user-facing concentration interpretation.",
        json_schema_extra={"example": "Apple Inc."},
    )
    quantity: float | None = Field(
        default=None,
        description="Baseline quantity for the position.",
        json_schema_extra={"example": 1000.0},
    )
    market_value_base: float | None = Field(
        default=None,
        description="Optional baseline market value in reporting currency.",
        json_schema_extra={"example": 19500.25},
    )
    weight: float | None = Field(
        default=None,
        description="Optional baseline portfolio weight for this position.",
        json_schema_extra={"example": 0.1245},
    )
    issuer_id: str | None = Field(
        default=None,
        description="Optional canonical issuer identifier for issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_INC"},
    )
    ultimate_parent_issuer_id: str | None = Field(
        default=None,
        description="Optional ultimate parent issuer identifier for parent-level issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_HOLDING"},
    )


class ProjectedPosition(BaseModel):
    security_id: str = Field(
        description="Canonical security identifier in the projected portfolio state.",
        json_schema_extra={"example": "AAPL.US"},
    )
    security_name: str | None = Field(
        default=None,
        description="Optional projected security display name for user-facing concentration interpretation.",
        json_schema_extra={"example": "Apple Inc."},
    )
    proposed_quantity: float | None = Field(
        default=None,
        description="Projected quantity for simulation or concentration what-if analysis.",
        json_schema_extra={"example": 1200.0},
    )
    projected_market_value_base: float | None = Field(
        default=None,
        description="Optional projected market value in reporting currency.",
        json_schema_extra={"example": 23400.3},
    )
    projected_weight: float | None = Field(
        default=None,
        description="Optional projected portfolio weight for this position.",
        json_schema_extra={"example": 0.142},
    )
    issuer_id: str | None = Field(
        default=None,
        description="Optional canonical issuer identifier for issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_INC"},
    )
    ultimate_parent_issuer_id: str | None = Field(
        default=None,
        description="Optional ultimate parent issuer identifier for parent-level issuer concentration grouping.",
        json_schema_extra={"example": "ISSUER_APPLE_HOLDING"},
    )


class IssuerMappingInput(BaseModel):
    security_id: str = Field(
        description="Security identifier mapped to issuer keys for concentration enrichment overrides.",
        json_schema_extra={"example": "SEC_AAPL_US"},
    )
    issuer_id: str | None = Field(
        default=None,
        description="Legal issuer identifier mapped to this security.",
        json_schema_extra={"example": "ISSUER_APPLE_INC"},
    )
    issuer_name: str | None = Field(
        default=None,
        description="Legal issuer display name mapped to this security.",
        json_schema_extra={"example": "Apple Inc."},
    )
    ultimate_parent_issuer_id: str | None = Field(
        default=None,
        description="Ultimate parent issuer identifier mapped to this security.",
        json_schema_extra={"example": "ISSUER_APPLE_HOLDING"},
    )
    ultimate_parent_issuer_name: str | None = Field(
        default=None,
        description="Ultimate parent issuer display name mapped to this security.",
        json_schema_extra={"example": "Apple Holdings PLC"},
    )


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


class StatefulConcentrationInput(BaseModel):
    portfolio_id: str = Field(
        description="Portfolio identifier resolved through lotus-core.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    as_of_date: date = Field(
        description="Business date used to resolve baseline positions from lotus-core.",
        json_schema_extra={"example": "2026-02-27"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Optional reporting currency override. Defaults to portfolio currency.",
        json_schema_extra={"example": "USD"},
    )
    include_cash_positions: bool = Field(
        default=True,
        description="Whether cash-class positions are included in concentration inputs.",
        json_schema_extra={"example": True},
    )
    include_zero_quantity_positions: bool = Field(
        default=False,
        description="Whether zero-quantity positions are included in concentration inputs.",
        json_schema_extra={"example": False},
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Top-N bucket used for single-position concentration aggregates.",
        json_schema_extra={"example": 10},
    )
    issuer_mappings: list[IssuerMappingInput] = Field(
        default_factory=list,
        description=(
            "Optional caller-provided issuer mappings keyed by security_id. "
            "Used according to enrichment_policy when computing issuer concentration."
        ),
        json_schema_extra={
            "example": [
                {
                    "security_id": "SEC_AAPL_US",
                    "issuer_id": "ISSUER_APPLE_INC",
                    "issuer_name": "Apple Inc.",
                    "ultimate_parent_issuer_id": "ISSUER_APPLE_HOLDING",
                    "ultimate_parent_issuer_name": "Apple Holdings PLC",
                }
            ]
        },
    )


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
    price: float | None = Field(
        default=None,
        description="Optional transaction price used by lotus-core simulation change model.",
        json_schema_extra={"example": 195.05},
    )
    amount: float | None = Field(
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
                "simulation_changes": [{"security_id": "SEC_AAPL_US", "transaction_type": "BUY"}],
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
