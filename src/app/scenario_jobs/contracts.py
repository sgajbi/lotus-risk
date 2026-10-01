from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.contracts.scenario_inputs import (
    SCENARIO_MAX_EXPOSURE_BUCKETS,
    ScenarioExposure,
    ScenarioExposureComponent,
    _validate_full_allocation,
)
from app.contracts.scenario_request_field_examples import (
    SCENARIO_EXPOSURE_COMPONENTS_EXAMPLE,
    SCENARIO_EXPOSURES_EXAMPLE,
)
from app.contracts.scenario_response_outputs import RegimeScenarioPackResponse
from app.contracts.scenario_result_outputs import ScenarioPositionContribution

SCENARIO_JOB_MAX_EXPOSURE_COMPONENTS = 1_000


def _validate_exposure_buckets(exposures: list[ScenarioExposure]) -> None:
    if not exposures:
        raise ValueError("exposures must contain at least one scenario exposure bucket")
    normalized_buckets = [exposure.bucket.upper() for exposure in exposures]
    duplicate_buckets = sorted(
        {bucket for bucket in normalized_buckets if normalized_buckets.count(bucket) > 1}
    )
    if duplicate_buckets:
        raise ValueError(
            "exposures must contain unique scenario buckets: " + ", ".join(duplicate_buckets)
        )
    _validate_full_allocation(
        weights=[exposure.weight for exposure in exposures],
        field_name="exposures",
    )


def _validate_exposure_components(
    *,
    exposures: list[ScenarioExposure],
    exposure_components: list[ScenarioExposureComponent],
) -> None:
    exposure_by_bucket = {exposure.bucket.upper(): exposure.weight for exposure in exposures}
    component_totals: dict[str, float] = {}
    for component in exposure_components:
        bucket = component.bucket.upper()
        component_totals[bucket] = component_totals.get(bucket, 0.0) + component.weight
    unknown_buckets = sorted(set(component_totals) - set(exposure_by_bucket))
    if unknown_buckets:
        raise ValueError(
            "exposure_components contain buckets absent from exposures: "
            + ", ".join(unknown_buckets)
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
        weights=[component.weight for component in exposure_components],
        field_name="exposure_components",
    )


class ScenarioEvaluationJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class RegimeScenarioPackJobRequest(BaseModel):
    """Large-evaluation input retained verbatim before asynchronous execution."""

    scenario_pack_id: str = Field(
        description="Governed scenario pack identifier frozen with the submitted job.",
        json_schema_extra={"example": "CIO_REGIME_2026_Q2"},
    )
    portfolio_id: str | None = Field(
        default=None,
        description="Optional portfolio identifier retained as immutable lineage.",
        json_schema_extra={"example": "PB_SG_GLOBAL_BAL_001"},
    )
    as_of_date: dt.date = Field(
        description="Business date frozen with the large scenario evaluation input.",
        json_schema_extra={"example": "2026-05-03"},
    )
    exposures: list[ScenarioExposure] = Field(
        max_length=SCENARIO_MAX_EXPOSURE_BUCKETS,
        description="Reconciled bucket weights forming one full portfolio allocation.",
        json_schema_extra={"example": SCENARIO_EXPOSURES_EXAMPLE},
    )
    exposure_components: list[ScenarioExposureComponent] = Field(
        default_factory=list,
        max_length=SCENARIO_JOB_MAX_EXPOSURE_COMPONENTS,
        description=(
            "Optional reconciled position rows, bounded to 1,000 for durable job admission. "
            "This admission slice does not yet execute or page their contributions."
        ),
        json_schema_extra={"example": SCENARIO_EXPOSURE_COMPONENTS_EXAMPLE},
    )
    maximum_allowed_loss_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Consumer policy threshold retained for the eventual evaluation.",
        json_schema_extra={"example": 0.12},
    )

    @model_validator(mode="after")
    def validate_exposures(self) -> RegimeScenarioPackJobRequest:
        _validate_exposure_buckets(self.exposures)
        if self.exposure_components:
            _validate_exposure_components(
                exposures=self.exposures,
                exposure_components=self.exposure_components,
            )
        return self


class ScenarioEvaluationJobAccepted(BaseModel):
    job_id: str = Field(
        description="Stable tenant-scoped immutable scenario job identity.",
        json_schema_extra={"example": "12db0287-38f2-4c29-a155-61499ea40b47"},
    )
    status: ScenarioEvaluationJobStatus = Field(
        description="Durable lifecycle posture; this slice only emits QUEUED.",
        json_schema_extra={"example": "QUEUED"},
    )
    request_fingerprint: str = Field(
        description="SHA-256 fingerprint of the canonical immutable request.",
        json_schema_extra={
            "example": "sha256:7a0b1c4dfe3189b80d30c7d2a258caa4d9e5a43094e4efc91295ab30aa12bb12"
        },
    )
    scenario_pack_revision: str = Field(
        description="SHA-256 revision of the exact code-defined scenario pack admitted.",
        json_schema_extra={
            "example": "sha256:2c7b69ddccf6ea6fdfbe09de286c2c853baa1698f1d36f10cbf64fcde8d3fa82"
        },
    )
    expires_at: dt.datetime = Field(
        description="Configured expiry of retained immutable admission evidence.",
        json_schema_extra={"example": "2026-05-06T09:30:00Z"},
    )


class ScenarioEvaluationJobStatusResponse(ScenarioEvaluationJobAccepted):
    submitted_at: dt.datetime = Field(
        description="UTC timestamp at the immutable admission transaction boundary.",
        json_schema_extra={"example": "2026-05-03T09:30:00Z"},
    )
    failure_code: str | None = Field(
        default=None,
        description=(
            "Qualified terminal failure code. This is absent while work is queued or running and "
            "does not expose another tenant's evidence."
        ),
        json_schema_extra={"example": "SCENARIO_PACK_REVISION_UNAVAILABLE"},
    )
    result: RegimeScenarioPackResponse | None = Field(
        default=None,
        description=(
            "Immutable aggregate scenario evaluation after successful completion. Position "
            "contributions are deliberately retrieved from the bounded contribution page route."
        ),
        json_schema_extra={"example": {}},
    )


class ScenarioEvaluationJobContribution(ScenarioPositionContribution):
    scenario_id: str = Field(
        description="Immutable governed scenario identity for this contribution row.",
        json_schema_extra={"example": "growth_slowdown"},
    )


class ScenarioEvaluationJobContributionPage(BaseModel):
    job_id: str = Field(
        description="Stable identity of the completed scenario evaluation job.",
        json_schema_extra={"example": "12db0287-38f2-4c29-a155-61499ea40b47"},
    )
    contributions: list[ScenarioEvaluationJobContribution] = Field(
        description="One stable, bounded page of immutable source-owned contribution rows.",
        json_schema_extra={
            "example": [
                {
                    "scenario_id": "growth_slowdown",
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
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next stable page, or null when the result is exhausted.",
        json_schema_extra={"example": "WyJncm93dGhfc2xvd2Rvd24iLDI0OV0"},
    )


__all__ = [
    "SCENARIO_JOB_MAX_EXPOSURE_COMPONENTS",
    "RegimeScenarioPackJobRequest",
    "ScenarioEvaluationJobAccepted",
    "ScenarioEvaluationJobContribution",
    "ScenarioEvaluationJobContributionPage",
    "ScenarioEvaluationJobStatus",
    "ScenarioEvaluationJobStatusResponse",
]
