from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.risk import RiskRequestScope
from app.contracts.rolling_examples import ROLLING_RESPONSE_EXAMPLE
from app.contracts.rolling_inputs import RollingInputMode
from app.contracts.rolling_metadata_outputs import RollingMetadata
from app.contracts.rolling_period_outputs import RollingPeriodResult
from app.contracts.rolling_response_field_examples import (
    ROLLING_RESPONSE_METADATA_EXAMPLE,
    ROLLING_RESPONSE_RESULTS_EXAMPLE,
    ROLLING_RESPONSE_SCOPE_EXAMPLE,
)


class RollingResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this rolling analytics response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: RollingInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateless"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for rolling calculations.",
        json_schema_extra={"example": ROLLING_RESPONSE_SCOPE_EXAMPLE},
    )
    results: dict[str, RollingPeriodResult] = Field(
        description="Rolling metric period results keyed by period name.",
        json_schema_extra={"example": ROLLING_RESPONSE_RESULTS_EXAMPLE},
    )
    metadata: RollingMetadata = Field(
        description="Rolling metric contract and methodology metadata.",
        json_schema_extra={"example": ROLLING_RESPONSE_METADATA_EXAMPLE},
    )

    model_config = ConfigDict(json_schema_extra={"example": cast(Any, ROLLING_RESPONSE_EXAMPLE)})


__all__ = ["RollingResponse"]
