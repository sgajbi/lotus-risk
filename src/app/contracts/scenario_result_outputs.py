from __future__ import annotations

from pydantic import BaseModel, Field


class ScenarioPositionContribution(BaseModel):
    security_id: str = Field(
        description="Security or instrument identifier for the scenario contribution row.",
        json_schema_extra={"example": "FO_EQ_AAPL_US"},
    )
    display_name: str | None = Field(
        default=None,
        description="Optional display name for the contributing security or instrument.",
        json_schema_extra={"example": "Apple Inc."},
    )
    bucket: str = Field(
        description="Scenario bucket used to assign the risk shock.",
        json_schema_extra={"example": "EQUITY"},
    )
    weight: float = Field(
        ge=0.0,
        description="Portfolio weight used for this security contribution.",
        json_schema_extra={"example": 0.18},
    )
    shock_pct: float = Field(
        description="Scenario shock ratio applied to the security contribution bucket.",
        json_schema_extra={"example": -0.12},
    )
    contribution_loss_pct: float = Field(
        ge=0.0,
        description="Non-negative contribution to expected portfolio loss under the scenario.",
        json_schema_extra={"example": 0.0216},
    )


class ScenarioResult(BaseModel):
    scenario_id: str = Field(
        description="Scenario identifier within the governed pack.",
        json_schema_extra={"example": "growth_slowdown"},
    )
    display_name: str = Field(
        description="Scenario display name.",
        json_schema_extra={"example": "Growth slowdown"},
    )
    expected_loss_pct: float = Field(
        description="Expected portfolio loss ratio under this scenario.",
        json_schema_extra={"example": 0.0845},
    )
    shock_by_bucket: dict[str, float] = Field(
        description="Scenario shock ratios by exposure bucket.",
        json_schema_extra={"example": {"EQUITY": -0.12, "FIXED_INCOME": -0.03}},
    )
    position_contributions: list[ScenarioPositionContribution] = Field(
        default_factory=list,
        description=(
            "Optional per-security contribution rows when exposure_components were supplied. "
            "Rows are source-owned scenario contribution evidence, not a full repricing model."
        ),
        json_schema_extra={
            "example": [
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "display_name": "Apple Inc.",
                    "bucket": "EQUITY",
                    "weight": 0.18,
                    "shock_pct": -0.12,
                    "contribution_loss_pct": 0.0216,
                }
            ]
        },
    )


__all__ = [
    "ScenarioPositionContribution",
    "ScenarioResult",
]
