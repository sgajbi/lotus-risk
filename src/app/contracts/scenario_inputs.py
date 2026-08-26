from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.contracts.scenario_request_field_examples import (
    SCENARIO_EXPOSURE_COMPONENTS_EXAMPLE,
    SCENARIO_EXPOSURES_EXAMPLE,
)

SCENARIO_ALLOCATION_TOLERANCE = 0.000001
SCENARIO_MAX_EXPOSURE_BUCKETS = 16
SCENARIO_MAX_EXPOSURE_COMPONENTS = 250
SCENARIO_MAX_POSITION_CONTRIBUTION_ROWS = SCENARIO_MAX_EXPOSURE_COMPONENTS


def _validate_full_allocation(*, weights: list[float], field_name: str) -> None:
    total = sum(weights)
    if abs(total - 1.0) > SCENARIO_ALLOCATION_TOLERANCE:
        raise ValueError(
            f"{field_name} weights must sum to 1.0 within "
            f"{SCENARIO_ALLOCATION_TOLERANCE}; received {total:.6f}"
        )


class ScenarioExposure(BaseModel):
    bucket: str = Field(
        description="Risk scenario exposure bucket.",
        json_schema_extra={"example": "EQUITY"},
    )
    weight: float = Field(
        ge=0.0,
        le=1.0,
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
        le=1.0,
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
        max_length=SCENARIO_MAX_EXPOSURE_BUCKETS,
        description=(
            "Caller-supplied portfolio exposure weights by scenario bucket. Weights must form a "
            "full allocation that sums to 1.0 within the governed tolerance."
        ),
        json_schema_extra={"example": SCENARIO_EXPOSURES_EXAMPLE},
    )
    exposure_components: list[ScenarioExposureComponent] = Field(
        default_factory=list,
        max_length=SCENARIO_MAX_EXPOSURE_COMPONENTS,
        description=(
            "Optional position-level exposure components used to emit per-security scenario "
            "contribution rows. When supplied, component weights must reconcile to the bucket "
            "weights in exposures. Runtime evaluation enforces a scenario-pack-aware component "
            "count so returned position contribution rows remain bounded by the "
            f"{SCENARIO_MAX_POSITION_CONTRIBUTION_ROWS} row limit."
        ),
        json_schema_extra={"example": SCENARIO_EXPOSURE_COMPONENTS_EXAMPLE},
    )
    maximum_allowed_loss_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Maximum permitted scenario loss ratio for the consumer policy.",
        json_schema_extra={"example": 0.12},
    )

    @model_validator(mode="after")
    def validate_exposures(self) -> RegimeScenarioPackRequest:
        if not self.exposures:
            raise ValueError("exposures must contain at least one scenario exposure bucket")
        normalized_buckets = [exposure.bucket.upper() for exposure in self.exposures]
        duplicate_buckets = sorted(
            {bucket for bucket in normalized_buckets if normalized_buckets.count(bucket) > 1}
        )
        if duplicate_buckets:
            raise ValueError(
                "exposures must contain unique scenario buckets: " + ", ".join(duplicate_buckets)
            )
        _validate_full_allocation(
            weights=[exposure.weight for exposure in self.exposures],
            field_name="exposures",
        )
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
            _validate_full_allocation(
                weights=[component.weight for component in self.exposure_components],
                field_name="exposure_components",
            )
        return self


__all__ = [
    "SCENARIO_ALLOCATION_TOLERANCE",
    "SCENARIO_MAX_EXPOSURE_BUCKETS",
    "SCENARIO_MAX_EXPOSURE_COMPONENTS",
    "SCENARIO_MAX_POSITION_CONTRIBUTION_ROWS",
    "RegimeScenarioPackRequest",
    "ScenarioExposure",
    "ScenarioExposureComponent",
]
