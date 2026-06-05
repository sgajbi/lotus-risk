from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator


class ScenarioExposure(BaseModel):
    bucket: str = Field(
        description="Risk scenario exposure bucket.",
        json_schema_extra={"example": "EQUITY"},
    )
    weight: float = Field(
        ge=0.0,
        description="Portfolio weight for this exposure bucket.",
        json_schema_extra={"example": 0.55},
    )


class ScenarioExposureComponent(BaseModel):
    security_id: str = Field(
        description="Security or instrument identifier contributing to the scenario bucket.",
        json_schema_extra={"example": "FO_EQ_AAPL_US"},
    )
    display_name: str | None = Field(
        default=None,
        description="Optional display name for the contributing security or instrument.",
        json_schema_extra={"example": "Apple Inc."},
    )
    bucket: str = Field(
        description="Scenario bucket used for the security contribution.",
        json_schema_extra={"example": "EQUITY"},
    )
    weight: float = Field(
        ge=0.0,
        description="Portfolio weight represented by this security contribution.",
        json_schema_extra={"example": 0.18},
    )


class RegimeScenarioPackRequest(BaseModel):
    scenario_pack_id: str = Field(
        description="Governed scenario pack identifier.",
        json_schema_extra={"example": "CIO_REGIME_2026_Q2"},
    )
    portfolio_id: str | None = Field(
        default=None,
        description="Optional portfolio identifier used for lineage and diagnostics.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date for the scenario-pack evaluation.",
        json_schema_extra={"example": "2026-05-03"},
    )
    exposures: list[ScenarioExposure] = Field(
        description="Caller-supplied portfolio exposure weights by scenario bucket.",
        json_schema_extra={
            "example": [
                {"bucket": "EQUITY", "weight": 0.55},
                {"bucket": "FIXED_INCOME", "weight": 0.35},
                {"bucket": "CASH", "weight": 0.10},
            ]
        },
    )
    exposure_components: list[ScenarioExposureComponent] = Field(
        default_factory=list,
        description=(
            "Optional position-level exposure components used to emit per-security scenario "
            "contribution rows. When supplied, component weights must reconcile to the bucket "
            "weights in exposures."
        ),
        json_schema_extra={
            "example": [
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "display_name": "Apple Inc.",
                    "bucket": "EQUITY",
                    "weight": 0.18,
                },
                {
                    "security_id": "FO_BOND_UST_2030",
                    "display_name": "United States Treasury 3.875% 2030",
                    "bucket": "FIXED_INCOME",
                    "weight": 0.35,
                },
            ]
        },
    )
    maximum_allowed_loss_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Maximum permitted scenario loss ratio for the consumer policy.",
        json_schema_extra={"example": 0.12},
    )

    @model_validator(mode="after")
    def validate_exposures(self) -> "RegimeScenarioPackRequest":
        if not self.exposures:
            raise ValueError("exposures must contain at least one scenario exposure bucket")
        if self.exposure_components:
            exposure_by_bucket = {
                exposure.bucket.upper(): exposure.weight for exposure in self.exposures
            }
            component_totals: dict[str, float] = {}
            for component in self.exposure_components:
                bucket = component.bucket.upper()
                component_totals[bucket] = component_totals.get(bucket, 0.0) + component.weight
            unknown_component_buckets = sorted(set(component_totals) - set(exposure_by_bucket))
            if unknown_component_buckets:
                raise ValueError(
                    "exposure_components contain buckets absent from exposures: "
                    + ", ".join(unknown_component_buckets)
                )
            mismatched_buckets = [
                bucket
                for bucket, component_weight in sorted(component_totals.items())
                if abs(component_weight - exposure_by_bucket[bucket]) > 0.000001
            ]
            if mismatched_buckets:
                raise ValueError(
                    "exposure_components must reconcile to exposures for buckets: "
                    + ", ".join(mismatched_buckets)
                )
        return self
