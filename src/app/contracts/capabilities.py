from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_FEATURE_KEYS: tuple[str, ...] = (
    "risk.analytics.risk_analytics",
    "risk.analytics.concentration",
    "risk.analytics.metrics",
)
CAPABILITY_WORKFLOW_KEYS: tuple[str, ...] = (
    "risk_snapshot",
    "concentration_risk",
)
SupportedInputMode = Literal["stateless", "stateful", "simulation"]


class CapabilityFeature(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    enabled: bool = True


class CapabilityWorkflow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workflow_key: str = Field(alias="workflow_key")
    enabled: bool = True


class IntegrationCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_service: str = Field(alias="sourceService")
    policy_version: str = Field(alias="policyVersion")
    supported_input_modes: list[SupportedInputMode] = Field(alias="supportedInputModes")
    features: list[CapabilityFeature]
    workflows: list[CapabilityWorkflow]
