from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CAPABILITY_FEATURE_KEYS: tuple[str, ...] = (
    "risk.analytics.risk_analytics",
    "risk.analytics.concentration",
    "risk.analytics.drawdown",
    "risk.analytics.rolling_metrics",
    "risk.analytics.metrics",
)
CAPABILITY_WORKFLOW_KEYS: tuple[str, ...] = (
    "risk_snapshot",
    "concentration_risk",
    "drawdown_analytics",
    "rolling_risk_analytics",
)
SupportedInputMode = Literal["stateless", "stateful", "simulation"]


class CapabilityFeature(BaseModel):
    key: str = Field(
        description="Canonical feature identifier exposed by lotus-risk.",
        json_schema_extra={"example": "risk.analytics.risk_analytics"},
    )
    enabled: bool = Field(
        default=True,
        description="Whether this feature is currently enabled.",
        json_schema_extra={"example": True},
    )


class CapabilityWorkflow(BaseModel):
    workflow_key: str = Field(
        description="Canonical workflow key exposed by lotus-risk.",
        json_schema_extra={"example": "risk_snapshot"},
    )
    enabled: bool = Field(
        default=True,
        description="Whether this workflow is currently enabled.",
        json_schema_extra={"example": True},
    )


class IntegrationCapabilitiesResponse(BaseModel):
    source_service: str = Field(
        description="Service identifier publishing this capabilities contract.",
        json_schema_extra={"example": "lotus-risk"},
    )
    policy_version: str = Field(
        description="Capabilities policy version used by this service.",
        json_schema_extra={"example": "risk.v1"},
    )
    supported_input_modes: list[SupportedInputMode] = Field(
        description="Execution modes supported by lotus-risk API contracts.",
        json_schema_extra={"example": ["stateless", "stateful", "simulation"]},
    )
    features: list[CapabilityFeature] = Field(
        description="Feature-level capability switches.",
        json_schema_extra={"example": [{"key": "risk.analytics.risk_analytics", "enabled": True}]},
    )
    workflows: list[CapabilityWorkflow] = Field(
        description="Workflow-level capability switches.",
        json_schema_extra={"example": [{"workflow_key": "risk_snapshot", "enabled": True}]},
    )
