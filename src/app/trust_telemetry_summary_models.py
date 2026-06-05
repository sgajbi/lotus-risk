from __future__ import annotations

from pydantic import BaseModel, Field


class TrustTelemetryReviewSummary(BaseModel):
    declared_product_count: int = Field(
        description="Number of repo-native declared producer products included in the snapshot.",
        json_schema_extra={"example": 7},
    )
    declared_dependency_count: int = Field(
        description="Number of repo-native declared upstream dependencies included in the snapshot.",
        json_schema_extra={"example": 6},
    )
    degraded_dependency_count: int = Field(
        description="Count of declared upstream dependencies whose producer runtime status is degraded.",
        json_schema_extra={"example": 1},
    )
    unavailable_dependency_count: int = Field(
        description="Count of declared upstream dependencies whose producer runtime status is unavailable.",
        json_schema_extra={"example": 0},
    )
    missing_runtime_service_count: int = Field(
        description="Count of declared upstream dependencies whose producer service has no current runtime view.",
        json_schema_extra={"example": 0},
    )
    degraded_dependency_products: list[str] = Field(
        default_factory=list,
        description="Declared upstream product names currently backed by degraded producer services.",
        json_schema_extra={"example": ["ReturnsSeriesBundle"]},
    )
    unavailable_dependency_products: list[str] = Field(
        default_factory=list,
        description="Declared upstream product names currently backed by unavailable producer services.",
        json_schema_extra={"example": []},
    )
    missing_runtime_services: list[str] = Field(
        default_factory=list,
        description="Declared upstream producer services that currently have no runtime view.",
        json_schema_extra={"example": []},
    )
