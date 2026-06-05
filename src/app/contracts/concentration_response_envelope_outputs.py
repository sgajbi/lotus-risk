from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.concentration_examples import CONCENTRATION_RESPONSE_EXAMPLES
from app.contracts.concentration_inputs import ConcentrationInputMode
from app.contracts.concentration_metadata_outputs import ConcentrationMetadata
from app.contracts.concentration_metric_outputs import (
    ConcentrationRiskProxy,
    IssuerConcentration,
    SinglePositionConcentration,
)
from app.contracts.concentration_response_contexts import ConcentrationValuationContext
from app.contracts.concentration_response_field_examples import (
    CONCENTRATION_ISSUER_EXAMPLE,
    CONCENTRATION_METADATA_EXAMPLE,
    CONCENTRATION_RISK_PROXY_EXAMPLE,
    CONCENTRATION_SINGLE_POSITION_EXAMPLE,
    CONCENTRATION_VALUATION_CONTEXT_EXAMPLE,
)


class ConcentrationResponse(BaseModel):
    source_service: str = Field(
        description="Service identifier that produced this concentration analytics result.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: ConcentrationInputMode = Field(
        description="Execution mode used for this concentration response.",
        json_schema_extra={"example": "simulation"},
    )
    risk_proxy: ConcentrationRiskProxy = Field(
        description="HHI concentration risk analytics payload.",
        json_schema_extra={"example": CONCENTRATION_RISK_PROXY_EXAMPLE},
    )
    single_position_concentration: SinglePositionConcentration = Field(
        description="Single-position concentration analytics payload.",
        json_schema_extra={"example": CONCENTRATION_SINGLE_POSITION_EXAMPLE},
    )
    issuer_concentration: IssuerConcentration = Field(
        description="Issuer-level concentration analytics payload with coverage diagnostics.",
        json_schema_extra={"example": CONCENTRATION_ISSUER_EXAMPLE},
    )
    valuation_context: ConcentrationValuationContext | None = Field(
        default=None,
        description="Valuation context sourced from lotus-core for stateful/simulation mode.",
        json_schema_extra={"example": CONCENTRATION_VALUATION_CONTEXT_EXAMPLE},
    )
    metadata: ConcentrationMetadata | None = Field(
        default=None,
        description="Execution metadata for stateful/simulation concentration calculations.",
        json_schema_extra={"example": CONCENTRATION_METADATA_EXAMPLE},
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": cast(Any, CONCENTRATION_RESPONSE_EXAMPLES)}
    )


__all__ = ["ConcentrationResponse"]
