from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "ConcentrationRequest":
        if self.input_mode == ConcentrationInputMode.STATELESS and self.stateless_input is None:
            self.stateless_input = StatelessConcentrationInput()

        if self.input_mode == ConcentrationInputMode.STATEFUL and self.stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")

        if self.input_mode == ConcentrationInputMode.SIMULATION and self.simulation_input is None:
            raise ValueError("simulation_input is required when input_mode=simulation")

        return self


class ConcentrationRiskProxy(BaseModel):
    hhi_current: float = Field(
        description="Current Herfindahl-Hirschman Index value (0 to 10000).",
        json_schema_extra={"example": 2450.0},
    )
    hhi_proposed: float = Field(
        description="Proposed Herfindahl-Hirschman Index after applying projected positions.",
        json_schema_extra={"example": 2710.0},
    )
    hhi_delta: float = Field(
        description="Difference between proposed and current concentration.",
        json_schema_extra={"example": 260.0},
    )


class SinglePositionConcentration(BaseModel):
    top_position_weight_current: float = Field(
        description="Highest single-position weight in baseline state.",
        json_schema_extra={"example": 0.1245},
    )
    top_position_weight_proposed: float = Field(
        description="Highest single-position weight in proposed state.",
        json_schema_extra={"example": 0.142},
    )
    top_position_weight_delta: float = Field(
        description="Difference between proposed and baseline top-position weights.",
        json_schema_extra={"example": 0.0175},
    )
    top_n_cumulative_weight_current: float = Field(
        description="Cumulative baseline weight of top-N positions.",
        json_schema_extra={"example": 0.4123},
    )
    top_n_cumulative_weight_proposed: float = Field(
        description="Cumulative proposed weight of top-N positions.",
        json_schema_extra={"example": 0.4551},
    )
    top_n_cumulative_weight_delta: float = Field(
        description="Difference between proposed and baseline top-N cumulative weights.",
        json_schema_extra={"example": 0.0428},
    )
    top_n: int = Field(
        description="Top-N parameter used for cumulative concentration calculations.",
        json_schema_extra={"example": 10},
    )


class IssuerCoverageStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class IssuerConcentration(BaseModel):
    hhi_current: float = Field(
        description="Issuer-level baseline HHI concentration (0 to 10000).",
        json_schema_extra={"example": 3200.0},
    )
    hhi_proposed: float = Field(
        description="Issuer-level proposed HHI concentration (0 to 10000).",
        json_schema_extra={"example": 3475.0},
    )
    hhi_delta: float = Field(
        description="Difference between proposed and baseline issuer-level HHI concentration.",
        json_schema_extra={"example": 275.0},
    )
    top_issuer_weight_current: float = Field(
        description="Highest issuer-level baseline concentration weight.",
        json_schema_extra={"example": 0.18},
    )
    top_issuer_weight_proposed: float = Field(
        description="Highest issuer-level proposed concentration weight.",
        json_schema_extra={"example": 0.21},
    )
    top_issuer_weight_delta: float = Field(
        description="Difference between proposed and baseline top issuer weights.",
        json_schema_extra={"example": 0.03},
    )
    coverage_status: IssuerCoverageStatus = Field(
        description="Coverage quality for issuer mapping used in issuer concentration calculations.",
        json_schema_extra={"example": "partial"},
    )
    covered_position_count_current: int = Field(
        description="Count of baseline positions included in issuer grouping.",
        json_schema_extra={"example": 25},
    )
    covered_position_count_proposed: int = Field(
        description="Count of proposed positions included in issuer grouping.",
        json_schema_extra={"example": 27},
    )
    total_position_count_current: int = Field(
        description="Total baseline positions evaluated for issuer coverage.",
        json_schema_extra={"example": 30},
    )
    total_position_count_proposed: int = Field(
        description="Total proposed positions evaluated for issuer coverage.",
        json_schema_extra={"example": 31},
    )
    note: str | None = Field(
        default=None,
        description="Optional diagnostics note when issuer coverage is partial or unavailable.",
        json_schema_extra={"example": "issuer_id missing in lotus-core instrument_enrichment"},
    )


class ConcentrationValuationContext(BaseModel):
    portfolio_currency: str | None = Field(
        default=None,
        description="Portfolio base currency provided by lotus-core valuation context.",
        json_schema_extra={"example": "EUR"},
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Reporting currency used for concentration valuation inputs.",
        json_schema_extra={"example": "USD"},
    )
    position_basis: str | None = Field(
        default=None,
        description="Position basis used by lotus-core snapshot response.",
        json_schema_extra={"example": "market_value_base"},
    )
    weight_basis: str | None = Field(
        default=None,
        description="Weight basis used by lotus-core snapshot response.",
        json_schema_extra={"example": "total_market_value_base"},
    )


class ConcentrationMetadata(BaseModel):
    as_of_date: date | None = Field(
        default=None,
        description="Business date used for baseline/proposed concentration inputs.",
        json_schema_extra={"example": "2026-02-27"},
    )
    portfolio_id: str | None = Field(
        default=None,
        description="Portfolio identifier when stateful or simulation mode is used.",
        json_schema_extra={"example": "DEMO_DPM_EUR_001"},
    )
    simulation_session_id: str | None = Field(
        default=None,
        description="Simulation session identifier for simulation mode responses.",
        json_schema_extra={"example": "SIM_0001"},
    )
    simulation_session_version: int | None = Field(
        default=None,
        description="Simulation session version resolved by lotus-core.",
        json_schema_extra={"example": 3},
    )
    session_expires_at: datetime | None = Field(
        default=None,
        description="Session expiration timestamp returned by lotus-core when session lifecycle is created.",
        json_schema_extra={"example": "2026-02-28T10:30:00Z"},
    )


class ConcentrationResponse(BaseModel):
    source_service: str = Field(
        description="Service identifier that produced this concentration analytics result.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: ConcentrationInputMode = Field(
        description="Execution mode used for this concentration response.",
        json_schema_extra={"example": "simulation"},
    )
    risk_proxy: ConcentrationRiskProxy = Field(
        description="HHI concentration risk analytics payload.",
        json_schema_extra={
            "example": {"hhi_current": 2450.0, "hhi_proposed": 2710.0, "hhi_delta": 260.0}
        },
    )
    single_position_concentration: SinglePositionConcentration = Field(
        description="Single-position concentration analytics payload.",
        json_schema_extra={
            "example": {
                "top_position_weight_current": 0.1245,
                "top_position_weight_proposed": 0.142,
                "top_position_weight_delta": 0.0175,
                "top_n_cumulative_weight_current": 0.4123,
                "top_n_cumulative_weight_proposed": 0.4551,
                "top_n_cumulative_weight_delta": 0.0428,
                "top_n": 10,
            }
        },
    )
    issuer_concentration: IssuerConcentration = Field(
        description="Issuer-level concentration analytics payload with coverage diagnostics.",
        json_schema_extra={
            "example": {
                "hhi_current": 3200.0,
                "hhi_proposed": 3475.0,
                "hhi_delta": 275.0,
                "top_issuer_weight_current": 0.18,
                "top_issuer_weight_proposed": 0.21,
                "top_issuer_weight_delta": 0.03,
                "coverage_status": "partial",
                "covered_position_count_current": 25,
                "covered_position_count_proposed": 27,
                "total_position_count_current": 30,
                "total_position_count_proposed": 31,
                "note": "issuer_id missing in lotus-core instrument_enrichment",
            }
        },
    )
    valuation_context: ConcentrationValuationContext | None = Field(
        default=None,
        description="Valuation context sourced from lotus-core for stateful/simulation mode.",
        json_schema_extra={
            "example": {
                "portfolio_currency": "EUR",
                "reporting_currency": "USD",
                "position_basis": "market_value_base",
                "weight_basis": "total_market_value_base",
            }
        },
    )
    metadata: ConcentrationMetadata | None = Field(
        default=None,
        description="Execution metadata for stateful/simulation concentration calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-27",
                "portfolio_id": "DEMO_DPM_EUR_001",
                "simulation_session_id": "SIM_0001",
                "simulation_session_version": 3,
                "session_expires_at": "2026-02-28T10:30:00Z",
            }
        },
    )
