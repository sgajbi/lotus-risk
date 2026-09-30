from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class StatefulReturnsSourceEvidence(BaseModel):
    """Validated, source-owned qualification for one stateful returns-series response.

    The evidence is deliberately separate from Risk's request fingerprint: the
    request tells us what Risk asked Performance to calculate, while these
    values identify and qualify what Performance actually returned.
    """

    source_service: Literal["lotus-performance"] = Field(
        description="Service that produced the consumed returns-series response.",
        json_schema_extra={"example": "lotus-performance"},
    )
    calculation_id: UUID = Field(
        description="Stable Performance calculation handle for the consumed source response.",
        json_schema_extra={"example": "00000000-0000-4000-8000-000000000001"},
    )
    contract_version: Literal["v1"] = Field(
        description="Supported Performance returns-series response contract version.",
        json_schema_extra={"example": "v1"},
    )
    input_fingerprint: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$",
        description="Performance-owned fingerprint of the executed source inputs.",
        json_schema_extra={"example": "sha256:" + "1" * 64},
    )
    calculation_hash: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$",
        description="Performance-owned calculation hash for the consumed response.",
        json_schema_extra={"example": "sha256:" + "2" * 64},
    )
    freshness: Literal["current", "stale"] = Field(
        description="Performance-declared freshness of the consumed source evidence.",
        json_schema_extra={"example": "current"},
    )
    requested_points: int = Field(
        ge=0,
        description="Requested source points after policy resolution.",
        json_schema_extra={"example": 65},
    )
    returned_points: int = Field(
        ge=0,
        description="Source points returned after policy resolution.",
        json_schema_extra={"example": 65},
    )
    missing_points: int = Field(
        ge=0,
        description="Source points still missing after policy resolution.",
        json_schema_extra={"example": 0},
    )
    coverage_ratio: float = Field(
        ge=0,
        le=1,
        description="Returned-to-requested source coverage as a decimal ratio.",
        json_schema_extra={"example": 1.0},
    )

    @model_validator(mode="after")
    def validate_coverage(self) -> StatefulReturnsSourceEvidence:
        if self.requested_points != self.returned_points + self.missing_points:
            raise ValueError("coverage counts do not reconcile")
        expected_ratio = (
            1.0 if self.requested_points == 0 else self.returned_points / self.requested_points
        )
        if abs(self.coverage_ratio - expected_ratio) > 1e-12:
            raise ValueError("coverage ratio does not reconcile with coverage counts")
        return self


__all__ = ["StatefulReturnsSourceEvidence"]
