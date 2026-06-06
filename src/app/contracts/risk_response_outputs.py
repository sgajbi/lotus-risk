from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.audit import AuditMetadataFields
from app.contracts.risk_examples import RISK_RESPONSE_EXAMPLE
from app.contracts.risk_inputs import RiskRequestScope
from app.contracts.risk_metric_outputs import RiskPeriodResult
from app.contracts.risk_response_contexts import (
    BenchmarkRequestContext,
    RiskCalculationSupportability,
    RiskFreeContext,
)
from app.contracts.risk_response_field_examples import (
    RISK_BENCHMARK_CONTEXT_EXAMPLE,
    RISK_CALCULATION_SUPPORTABILITY_EXAMPLE,
    RISK_FREE_CONTEXT_EXAMPLE,
    RISK_RESPONSE_METADATA_EXAMPLE,
    RISK_RESPONSE_RESULTS_EXAMPLE,
    RISK_RESPONSE_SCOPE_EXAMPLE,
)


class RiskResponseMetadata(AuditMetadataFields):
    contract_version: str = Field(
        default="v1",
        description="Risk analytics contract version.",
        json_schema_extra={"example": "v1"},
    )
    methodology_version: str = Field(
        default="risk.v1",
        description="Methodology version used for the risk engine.",
        json_schema_extra={"example": "risk.v1"},
    )
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"] = Field(
        default="DAILY",
        description="Applied return sampling frequency.",
        json_schema_extra={"example": "DAILY"},
    )
    annualization_factor: int = Field(
        default=252,
        description="Applied annualization factor after defaults or overrides.",
        json_schema_extra={"example": 252},
    )
    use_log_returns: bool = Field(
        default=False,
        description="Whether returns were transformed to log returns before metric evaluation.",
        json_schema_extra={"example": False},
    )
    risk_free_mode: Literal["ZERO", "ANNUAL_RATE"] = Field(
        default="ZERO",
        description="Applied risk-free mode for Sharpe calculations.",
        json_schema_extra={"example": "ZERO"},
    )
    risk_free_annual_rate: float | None = Field(
        default=None,
        description="Applied annual risk-free rate when risk_free_mode=ANNUAL_RATE.",
        json_schema_extra={"example": 0.01},
    )
    risk_free_context: RiskFreeContext = Field(
        default_factory=RiskFreeContext,
        description="Applied risk-free interpretation context for Sharpe calculations.",
        json_schema_extra={"example": RISK_FREE_CONTEXT_EXAMPLE},
    )
    benchmark_context: BenchmarkRequestContext = Field(
        default_factory=BenchmarkRequestContext,
        description="Benchmark dependency request context for this response.",
        json_schema_extra={"example": RISK_BENCHMARK_CONTEXT_EXAMPLE},
    )
    calculation_supportability: RiskCalculationSupportability = Field(
        default_factory=lambda: RiskCalculationSupportability(
            state="ready",
            reason="calculation_complete",
            freshness_bucket="unknown",
        ),
        description="Source-backed supportability posture for UI and operator consumption.",
        json_schema_extra={"example": RISK_CALCULATION_SUPPORTABILITY_EXAMPLE},
    )
    mar_annual_rate: float = Field(
        default=0.0,
        description="Applied annual minimum acceptable return for Sortino calculations.",
        json_schema_extra={"example": 0.0},
    )
    var_method: Literal["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"] = Field(
        default="HISTORICAL",
        description="Applied Value-at-Risk method.",
        json_schema_extra={"example": "HISTORICAL"},
    )
    var_confidence: float = Field(
        default=0.99,
        description="Applied Value-at-Risk confidence level.",
        json_schema_extra={"example": 0.95},
    )
    var_horizon_days: int = Field(
        default=1,
        description="Applied Value-at-Risk horizon in business days.",
        json_schema_extra={"example": 1},
    )


class RiskResponse(BaseModel):
    scope: RiskRequestScope = Field(
        description="Echoed normalized scope context used for calculation.",
        json_schema_extra={"example": RISK_RESPONSE_SCOPE_EXAMPLE},
    )
    results: dict[str, RiskPeriodResult] = Field(
        description="Risk results keyed by period name or period type.",
        json_schema_extra={"example": RISK_RESPONSE_RESULTS_EXAMPLE},
    )
    metadata: RiskResponseMetadata = Field(
        default_factory=RiskResponseMetadata,
        description="Risk contract and applied option metadata.",
        json_schema_extra={"example": RISK_RESPONSE_METADATA_EXAMPLE},
    )

    model_config = ConfigDict(json_schema_extra={"example": cast(Any, RISK_RESPONSE_EXAMPLE)})


__all__ = [
    "RiskResponse",
    "RiskResponseMetadata",
]
