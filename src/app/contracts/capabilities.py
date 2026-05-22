from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CAPABILITY_FEATURE_KEYS: tuple[str, ...] = (
    "risk.analytics.risk_analytics",
    "risk.analytics.concentration",
    "risk.analytics.drawdown",
    "risk.analytics.rolling_metrics",
    "risk.analytics.historical_attribution",
    "risk.analytics.mandate_risk_health_context",
    "risk.analytics.regime_scenario_pack",
    "risk.analytics.risk_event_affected_cohort",
    "risk.analytics.metrics",
    "risk.observability.calculation_supportability",
)
CAPABILITY_WORKFLOW_KEYS: tuple[str, ...] = (
    "risk_snapshot",
    "concentration_risk",
    "drawdown_analytics",
    "rolling_risk_analytics",
    "historical_risk_attribution",
    "mandate_risk_health_context",
    "regime_scenario_pack_evaluation",
    "risk_event_affected_cohort",
)
SupportedInputMode = Literal["stateless", "stateful", "simulation"]
WorkflowSupportStatus = Literal["full", "partial"]


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
    endpoint_path: str = Field(
        description="Primary API path implementing this workflow.",
        json_schema_extra={"example": "/analytics/risk/calculate"},
    )
    supported_input_modes: list[SupportedInputMode] = Field(
        description="Input modes supported by this workflow contract.",
        json_schema_extra={"example": ["stateless", "stateful"]},
    )
    support_status: WorkflowSupportStatus = Field(
        description="Whether the workflow is fully implemented or intentionally partial.",
        json_schema_extra={"example": "full"},
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Deterministic implementation notes or support boundaries for this workflow.",
        json_schema_extra={
            "example": [
                "stateful active-risk supports POSITION, SECTOR, ASSET_CLASS, and ISSUER",
                "issuer active-risk consumes lotus-performance benchmark exposure context issuer groups",
            ]
        },
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
        json_schema_extra={
            "example": [
                {
                    "workflow_key": "risk_snapshot",
                    "enabled": True,
                    "endpoint_path": "/analytics/risk/calculate",
                    "supported_input_modes": ["stateless", "stateful"],
                    "support_status": "full",
                    "notes": ["simulation is intentionally unsupported"],
                }
            ]
        },
    )
