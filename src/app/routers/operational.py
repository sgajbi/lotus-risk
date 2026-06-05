from collections.abc import Sequence

from fastapi import APIRouter, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.capabilities import (
    CAPABILITY_FEATURE_KEYS,
    CapabilityFeature,
    IntegrationCapabilitiesResponse,
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
from app.services.capability_workflows import build_capability_workflows
from app.trust_telemetry import (
    DeclaredProductTrustTelemetrySnapshot,
    build_declared_product_trust_telemetry_snapshot,
)

router = APIRouter()


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
        workflows=build_capability_workflows(),
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
