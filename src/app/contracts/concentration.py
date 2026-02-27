from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RiskPosition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    security_id: str = Field(alias="securityId")
    proposed_quantity: float | None = Field(default=None, alias="proposedQuantity")
    quantity: float | None = None


class ConcentrationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    current_positions: list[RiskPosition] = Field(default_factory=list, alias="currentPositions")
    projected_positions: list[RiskPosition] = Field(
        default_factory=list, alias="projectedPositions"
    )


class ConcentrationRiskProxy(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    hhi_current: float = Field(alias="hhiCurrent")
    hhi_proposed: float = Field(alias="hhiProposed")
    hhi_delta: float = Field(alias="hhiDelta")


class ConcentrationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_service: str = Field(alias="sourceService")
    risk_proxy: ConcentrationRiskProxy = Field(alias="riskProxy")
