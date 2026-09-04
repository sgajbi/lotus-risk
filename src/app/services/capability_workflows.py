from __future__ import annotations

from dataclasses import dataclass

from app.contracts.capabilities import (
    CapabilityWorkflow,
    SupportedInputMode,
    WorkflowSupportStatus,
)

SUPPORTED_INPUT_MODE_ORDER: tuple[SupportedInputMode, ...] = ("stateless", "stateful", "simulation")


@dataclass(frozen=True)
class _CapabilityWorkflowSpec:
    workflow_key: str
    endpoint_path: str
    supported_input_modes: list[SupportedInputMode]
    support_status: WorkflowSupportStatus
    notes: list[str]


_CAPABILITY_WORKFLOW_SPECS: tuple[_CapabilityWorkflowSpec, ...] = (
    _CapabilityWorkflowSpec(
        workflow_key="risk_snapshot",
        endpoint_path="/analytics/risk/calculate",
        supported_input_modes=["stateless", "stateful"],
        support_status="full",
        notes=[
            "simulation is intentionally unsupported",
            "benchmark-dependent metrics require benchmark returns",
            "VaR and expected shortfall are signed return-threshold metrics",
        ],
    ),
    _CapabilityWorkflowSpec(
        workflow_key="concentration_risk",
        endpoint_path="/analytics/risk/concentration",
        supported_input_modes=["stateless", "stateful", "simulation"],
        support_status="full",
        notes=[
            "simulation is supported only for concentration risk",
            "issuer concentration includes coverage diagnostics",
        ],
    ),
    _CapabilityWorkflowSpec(
        workflow_key="drawdown_analytics",
        endpoint_path="/analytics/risk/drawdown",
        supported_input_modes=["stateless", "stateful"],
        support_status="full",
        notes=["simulation is intentionally unsupported"],
    ),
    _CapabilityWorkflowSpec(
        workflow_key="rolling_risk_analytics",
        endpoint_path="/analytics/risk/rolling-metrics",
        supported_input_modes=["stateless", "stateful"],
        support_status="full",
        notes=[
            "simulation is intentionally unsupported",
            "stateful rolling Sharpe depends on risk-free series availability from lotus-core",
        ],
    ),
    _CapabilityWorkflowSpec(
        workflow_key="historical_risk_attribution",
        endpoint_path="/analytics/risk/historical-attribution",
        supported_input_modes=["stateless", "stateful"],
        support_status="partial",
        notes=[
            "simulation is intentionally unsupported",
            "stateful active-risk supports POSITION, SECTOR, ASSET_CLASS, and ISSUER",
            "issuer active-risk consumes lotus-performance benchmark exposure context issuer groups",
            "historical-attribution response metadata is the authoritative active-risk support contract",
            "attribution residual, reconciled_sum, and metadata.metric_unit_semantics must be preserved with contributors",
        ],
    ),
    _CapabilityWorkflowSpec(
        workflow_key="mandate_risk_health_context",
        endpoint_path="/analytics/risk/mandate-health-context",
        supported_input_modes=["stateless"],
        support_status="partial",
        notes=[
            "derives bounded mandate risk health from source-owned tracking-error methodology",
            "returns threshold posture, lineage, and non-claim reason codes for Manage consumption",
            "does not create mandate actions, rebalance waves, or client communication",
        ],
    ),
    _CapabilityWorkflowSpec(
        workflow_key="regime_scenario_pack_evaluation",
        endpoint_path="/analytics/risk/regime-scenario-pack/evaluate",
        supported_input_modes=["stateless"],
        support_status="full",
        notes=[
            "evaluates caller-supplied exposure weights against governed CIO scenario packs",
            "returns source-owned worst-case loss, per-security contribution rows when supplied, CIO approval/effective-period/applicability posture, policy breach posture, and lineage",
            "does not forecast market states or accept browser-owned scenario methodology",
        ],
    ),
    _CapabilityWorkflowSpec(
        workflow_key="risk_event_affected_cohort",
        endpoint_path="/analytics/risk/risk-event-cohorts/evaluate",
        supported_input_modes=["stateless"],
        support_status="partial",
        notes=[
            "evaluates candidate portfolios against governed risk-event definitions",
            "returns affected membership, exclusions, impact scores, source refs, and supportability",
            "does not create rebalance waves or own campaign approval workflow",
        ],
    ),
)


def build_capability_workflows() -> list[CapabilityWorkflow]:
    return [
        CapabilityWorkflow(
            workflow_key=spec.workflow_key,
            endpoint_path=spec.endpoint_path,
            supported_input_modes=list(spec.supported_input_modes),
            support_status=spec.support_status,
            notes=list(spec.notes),
        )
        for spec in _CAPABILITY_WORKFLOW_SPECS
    ]


def aggregate_supported_input_modes(
    workflows: list[CapabilityWorkflow],
) -> list[SupportedInputMode]:
    observed = {
        mode
        for workflow in workflows
        if workflow.enabled
        for mode in workflow.supported_input_modes
    }
    return [mode for mode in SUPPORTED_INPUT_MODE_ORDER if mode in observed]
