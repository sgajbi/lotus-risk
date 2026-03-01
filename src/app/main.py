from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts.capabilities import (
    CAPABILITY_FEATURE_KEYS,
    CAPABILITY_WORKFLOW_KEYS,
    CapabilityFeature,
    CapabilityWorkflow,
    IntegrationCapabilitiesResponse,
    SupportedInputMode,
)
from app.contracts.concentration import ConcentrationRequest, ConcentrationResponse
from app.contracts.error import ErrorResponse
from app.contracts.ops import OpsChecks, OpsResponse
from app.contracts.risk import RiskAnalyticsRequest, RiskInputMode, RiskResponse
from app.enterprise_readiness import (
    build_enterprise_audit_middleware,
    validate_enterprise_runtime_config,
)
from app.error_response import error_response
from app.integrations.lotus_core_client import LotusCoreClient
from app.middleware.correlation import CorrelationIdMiddleware
from app.services.concentration_engine import calculate_concentration
from app.services.risk_engine import calculate_risk

SERVICE_NAME = "lotus-risk"
SERVICE_VERSION = "0.1.0"
ROUNDING_POLICY_VERSION = "v1"
SUPPORTED_INPUT_MODES: tuple[SupportedInputMode, ...] = ("stateless", "stateful", "simulation")

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)
app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
validate_enterprise_runtime_config()
app.middleware("http")(build_enterprise_audit_middleware())
Instrumentator().instrument(app)


class HealthResponse(BaseModel):
    status: str = Field(
        description="Health status indicator.",
        json_schema_extra={"example": "ok"},
    )
    service: str = Field(
        description="Service identifier.",
        json_schema_extra={"example": "lotus-risk"},
    )


class LivenessResponse(BaseModel):
    status: str = Field(
        description="Liveness status indicator.",
        json_schema_extra={"example": "live"},
    )


class ReadinessResponse(BaseModel):
    status: str = Field(
        description="Readiness state.",
        json_schema_extra={"example": "ready"},
    )


class MetadataResponse(BaseModel):
    service: str = Field(
        description="Service identifier.",
        json_schema_extra={"example": "lotus-risk"},
    )
    version: str = Field(
        description="Service version string.",
        json_schema_extra={"example": "0.1.0"},
    )
    rounding_policy_version: str = Field(
        description="Rounding policy revision used by risk outputs.",
        json_schema_extra={"example": "v1"},
    )


ERROR_RESPONSE_400: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Invalid input for business rule evaluation.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Unsupported period type: BAD",
                    "correlation_id": "corr-123",
                }
            }
        }
    },
}
ERROR_RESPONSE_403: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Authorization denied by enterprise policy.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "AUTHORIZATION_DENIED",
                    "message": "authorization_policy_denied",
                    "correlation_id": "corr-123",
                    "details": {"reason": "missing_headers:x-actor-id"},
                }
            }
        }
    },
}
ERROR_RESPONSE_404: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Endpoint or resource not found.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Not Found",
                    "correlation_id": "corr-123",
                }
            }
        }
    },
}
ERROR_RESPONSE_422: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Request payload validation failed.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request validation failed",
                    "correlation_id": "corr-123",
                    "details": [
                        {"loc": ["body", "periods", 0, "to_date"], "msg": "Field required"}
                    ],
                }
            }
        }
    },
}
ERROR_RESPONSE_DEFAULT: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Unhandled service error.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "REQUEST_REJECTED",
                    "message": "Unexpected error",
                    "correlation_id": "corr-123",
                }
            }
        }
    },
}
STANDARD_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: ERROR_RESPONSE_400,
    403: ERROR_RESPONSE_403,
    404: ERROR_RESPONSE_404,
    422: ERROR_RESPONSE_422,
    "default": ERROR_RESPONSE_DEFAULT,
}


def _default_error_code(status_code: int) -> str:
    if status_code == status.HTTP_404_NOT_FOUND:
        return "RESOURCE_NOT_FOUND"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "AUTHORIZATION_DENIED"
    if status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        return "PAYLOAD_TOO_LARGE"
    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return "INVALID_REQUEST"
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "INVALID_INPUT"
    return "REQUEST_REJECTED"


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
    return error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="INVALID_REQUEST",
        message="Request validation failed",
        details=exc.errors(),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_starlette_http_exception(
    request: Request, exc: StarletteHTTPException
) -> Response:
    return error_response(
        request,
        status_code=exc.status_code,
        code=_default_error_code(exc.status_code),
        message=str(exc.detail),
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> Response:
    return error_response(
        request,
        status_code=exc.status_code,
        code=_default_error_code(exc.status_code),
        message=str(exc.detail),
    )


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> Response:
    return error_response(
        request,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="INVALID_INPUT",
        message=str(exc),
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health status",
    description="Returns basic service health for compatibility probes.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME)


@app.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description="Returns liveness status for container/orchestrator probes.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def health_live() -> LivenessResponse:
    return LivenessResponse(status="live")


@app.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Returns readiness status, including draining behavior.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def health_ready(response: Response) -> ReadinessResponse:
    if bool(getattr(app.state, "is_draining", False)):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="draining")
    return ReadinessResponse(status="ready")


@app.get(
    "/metadata",
    response_model=MetadataResponse,
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


@app.get(
    "/ops",
    response_model=OpsResponse,
    summary="Operational diagnostics",
    description="Returns consolidated operational diagnostics and execution modes.",
    tags=["operational"],
    responses=STANDARD_ERROR_RESPONSES,
)
async def ops() -> OpsResponse:
    is_draining = bool(getattr(app.state, "is_draining", False))
    return OpsResponse(
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        status="degraded" if is_draining else "ok",
        checks=OpsChecks(live=True, ready=not is_draining, draining=is_draining),
        input_modes=list(SUPPORTED_INPUT_MODES),
    )


@app.get(
    "/integration/capabilities",
    response_model=IntegrationCapabilitiesResponse,
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
        workflows=[
            CapabilityWorkflow(workflow_key=workflow_key)
            for workflow_key in CAPABILITY_WORKFLOW_KEYS
        ],
    )


@app.get(
    "/metrics",
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


@app.post(
    "/analytics/risk/concentration",
    response_model=ConcentrationResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate concentration risk analytics",
    tags=["risk-analytics"],
    description=(
        "Calculates concentration-risk HHI metrics from current and projected position "
        "weights. Returns current, proposed, and delta concentration."
    ),
)
async def analytics_risk_concentration(
    payload: ConcentrationRequest,
    request: Request,
) -> ConcentrationResponse:
    core_client = getattr(app.state, "lotus_core_client", None)
    if core_client is None:
        core_client = LotusCoreClient()
    return await calculate_concentration(
        payload,
        core_client=core_client,
        correlation_id=request.headers.get("X-Correlation-Id"),
        actor_id=request.headers.get("X-Actor-Id"),
    )


@app.post(
    "/analytics/risk/calculate",
    response_model=RiskResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate portfolio risk metrics",
    tags=["risk-analytics"],
    description=(
        "Calculates risk metrics from provided return series using stateless input mode. "
        "Supports EXPLICIT/YEAR/MTD/QTD/YTD/ONE_YEAR/THREE_YEAR/FIVE_YEAR/SI periods, "
        "all VaR methods (HISTORICAL/GAUSSIAN/CORNISH_FISHER), and benchmark-aware metrics."
    ),
)
async def analytics_risk_calculate(request: RiskAnalyticsRequest) -> RiskResponse:
    if request.input_mode != RiskInputMode.STATELESS:
        raise ValueError(
            f"input_mode={request.input_mode.value} is not implemented for /analytics/risk/calculate yet. "
            "Use input_mode=stateless in this slice."
        )
    stateless_input = request.stateless_input
    assert stateless_input is not None
    return calculate_risk(stateless_input)
