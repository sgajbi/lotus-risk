from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import APIRouter, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.capabilities import (
    CAPABILITY_FEATURE_KEYS,
    CapabilityFeature,
    CapabilityWorkflow,
    IntegrationCapabilitiesResponse,
    SupportedInputMode,
    WorkflowSupportStatus,
)
from app.contracts.ops import (
    DependencyStatus,
    HealthResponse,
    LivenessResponse,
    MetadataResponse,
    OpsChecks,
    OpsResponse,
    ReadinessResponse,
)
from app.ops_runtime import DependencyRuntimeView, resolve_ops_status, resolve_readiness_status
from app.service_metadata import (
    ROUNDING_POLICY_VERSION,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUPPORTED_INPUT_MODES,
)
from app.trust_telemetry import (
    DeclaredProductTrustTelemetrySnapshot,
    build_declared_product_trust_telemetry_snapshot,
)

router = APIRouter()


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
            "attribution residual and reconciled_sum must be preserved with contributors",
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


def _capability_workflows() -> list[CapabilityWorkflow]:
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


def _dependency_statuses(dependencies: Sequence[DependencyRuntimeView]) -> list[DependencyStatus]:
    return [
        DependencyStatus(
            service=dependency.service,
            base_url=dependency.base_url,
            status=dependency.status,
            detail=dependency.detail,
            category=dependency.category,
            issue_code=dependency.issue_code,
        )
        for dependency in dependencies
    ]


@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="getHealthStatus",
    summary="Health status",
    description="Returns basic service health for compatibility probes.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME)


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    operation_id="getLivenessStatus",
    summary="Liveness probe",
    description="Returns liveness status for container/orchestrator probes.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def health_live() -> LivenessResponse:
    return LivenessResponse(status="live")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    operation_id="getReadinessStatus",
    summary="Readiness probe",
    description="Returns readiness status, including draining behavior.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def health_ready(request: Request, response: Response) -> ReadinessResponse:
    status_code, readiness_status, dependencies = resolve_readiness_status(request.app)
    response.status_code = status_code
    return ReadinessResponse(
        status=readiness_status,
        dependencies=_dependency_statuses(dependencies),
    )


@router.get(
    "/metadata",
    response_model=MetadataResponse,
    operation_id="getServiceMetadata",
    summary="Service metadata",
    description="Returns service metadata and policy versions.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def metadata() -> MetadataResponse:
    return MetadataResponse(
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        rounding_policy_version=ROUNDING_POLICY_VERSION,
    )


@router.get(
    "/ops",
    response_model=OpsResponse,
    operation_id="getOperationalDiagnostics",
    summary="Operational diagnostics",
    description="Returns consolidated operational diagnostics and execution modes.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def ops(request: Request) -> OpsResponse:
    readiness_status_code, _, dependencies = resolve_readiness_status(request.app)
    ops_status, _ = resolve_ops_status(request.app)
    is_draining = bool(getattr(request.app.state, "is_draining", False))
    return OpsResponse(
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        status=ops_status,
        checks=OpsChecks(
            live=True,
            ready=readiness_status_code == status.HTTP_200_OK,
            draining=is_draining,
        ),
        input_modes=list(SUPPORTED_INPUT_MODES),
        dependencies=_dependency_statuses(dependencies),
    )


@router.get(
    "/ops/trust-telemetry",
    response_model=DeclaredProductTrustTelemetrySnapshot,
    operation_id="getTrustTelemetrySnapshot",
    summary="Local trust telemetry snapshot",
    description=(
        "Returns the current repo-owned raw trust telemetry seeds for each repo-native declared "
        "lotus-risk product. This is an operator-facing preparation seam for RFC-0087 and is not "
        "a platform-certified trust contract."
    ),
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def ops_trust_telemetry(request: Request) -> DeclaredProductTrustTelemetrySnapshot:
    return build_declared_product_trust_telemetry_snapshot(
        app=request.app,
        service_name=SERVICE_NAME,
    )


@router.get(
    "/integration/capabilities",
    response_model=IntegrationCapabilitiesResponse,
    operation_id="getIntegrationCapabilities",
    summary="Integration capabilities",
    description="Publishes lotus-risk capabilities used for cross-service orchestration.",
    tags=["integration"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def integration_capabilities() -> IntegrationCapabilitiesResponse:
    return IntegrationCapabilitiesResponse(
        source_service=SERVICE_NAME,
        policy_version="risk.v1",
        supported_input_modes=list(SUPPORTED_INPUT_MODES),
        features=[CapabilityFeature(key=feature_key) for feature_key in CAPABILITY_FEATURE_KEYS],
        workflows=_capability_workflows(),
    )


@router.get(
    "/metrics",
    operation_id="getPrometheusMetrics",
    summary="Prometheus metrics",
    description="Exposes Prometheus metrics for observability scraping.",
    tags=["operational"],
    responses={
        200: {
            "description": "Prometheus text metrics payload.",
            "content": {"text/plain": {"example": "# HELP process_cpu_seconds_total ..."}},
        },
        **STANDARD_ERROR_RESPONSES,
    },
)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
