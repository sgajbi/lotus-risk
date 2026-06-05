from __future__ import annotations

from pydantic import BaseModel, Field


class DeclaredConsumerDependencyTelemetry(BaseModel):
    product_name: str = Field(
        description="Governed upstream product required by lotus-risk.",
        json_schema_extra={"example": "ReturnsSeriesBundle"},
    )
    producer_repository: str = Field(
        description="Owning repository for the required upstream product.",
        json_schema_extra={"example": "lotus-performance"},
    )
    required_product_version: str = Field(
        description="Governed upstream product version required by lotus-risk.",
        json_schema_extra={"example": "v1"},
    )
    consumption_mode: str = Field(
        description="Declared consumption mode for the upstream dependency.",
        json_schema_extra={"example": "api_read"},
    )
    failure_posture: str = Field(
        description="Declared failure posture when the upstream dependency is unavailable or weak.",
        json_schema_extra={"example": "fail_closed"},
    )
    validation_lanes: list[str] = Field(
        default_factory=list,
        description="Validation lanes in which this dependency is expected to be checked.",
        json_schema_extra={"example": ["feature", "pr-merge"]},
    )
    required_trust_metadata: list[str] = Field(
        default_factory=list,
        description="Trust metadata required from the upstream product declaration.",
        json_schema_extra={"example": ["generated_at", "as_of_date", "correlation_id"]},
    )
    runtime_status: str | None = Field(
        default=None,
        description="Current runtime status observed for the declared upstream producer service.",
        json_schema_extra={"example": "degraded"},
    )
    runtime_detail: str | None = Field(
        default=None,
        description="Current runtime detail observed for the declared upstream producer service.",
        json_schema_extra={"example": "high_latency"},
    )
    runtime_category: str | None = Field(
        default=None,
        description="Current structured runtime issue category for the declared upstream producer service.",
        json_schema_extra={"example": "transport"},
    )
    runtime_issue_code: str | None = Field(
        default=None,
        description="Current machine-readable runtime issue code for the declared upstream producer service.",
        json_schema_extra={"example": "UPSTREAM_HIGH_LATENCY"},
    )
