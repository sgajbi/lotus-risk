from __future__ import annotations

from pydantic import BaseModel, Field


class RiskPosition(BaseModel):
    security_id: str = Field(
        description="Canonical security identifier in the portfolio position set.",
        json_schema_extra={"example": "AAPL.US"},
    )
    proposed_quantity: float | None = Field(
        default=None,
        description="Projected quantity used for simulation or concentration what-if analysis.",
        json_schema_extra={"example": 1200.0},
    )
    quantity: float | None = Field(
        default=None,
        description="Current quantity in the baseline portfolio state.",
        json_schema_extra={"example": 1000.0},
    )


class ConcentrationRequest(BaseModel):
    current_positions: list[RiskPosition] = Field(
        default_factory=list,
        description="Current portfolio positions used to compute baseline concentration.",
        json_schema_extra={"example": [{"security_id": "AAPL.US", "quantity": 1000.0}]},
    )
    projected_positions: list[RiskPosition] = Field(
        default_factory=list,
        description="Projected positions used to compute post-change concentration.",
        json_schema_extra={"example": [{"security_id": "AAPL.US", "proposed_quantity": 1200.0}]},
    )


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


class ConcentrationResponse(BaseModel):
    source_service: str = Field(
        description="Service identifier that produced this concentration analytics result.",
        json_schema_extra={"example": "lotus-risk"},
    )
    risk_proxy: ConcentrationRiskProxy = Field(
        description="Concentration risk analytics payload.",
        json_schema_extra={
            "example": {"hhi_current": 2450.0, "hhi_proposed": 2710.0, "hhi_delta": 260.0}
        },
    )
