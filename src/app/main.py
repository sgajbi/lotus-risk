from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator
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
from app.contracts.risk import RiskCalculationRequest, RiskResponse
from app.enterprise_readiness import (
    build_enterprise_audit_middleware,
    validate_enterprise_runtime_config,
)
from app.error_response import error_response
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
Instrumentator().instrument(app).expose(app)

ERROR_RESPONSE_400: dict[str, Any] = {
    "model": ErrorResponse,
    "description": "Invalid input for business rule evaluation.",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Unsupported period type: BAD",
                    "correlationId": "corr-123",
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
                    "correlationId": "corr-123",
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
                    "correlationId": "corr-123",
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
                    "correlationId": "corr-123",
                    "details": [{"loc": ["body", "periods", 0, "toDate"], "msg": "Field required"}],
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, str]:
    if bool(getattr(app.state, "is_draining", False)):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "draining"}
    return {"status": "ready"}


@app.get("/metadata")
async def metadata() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "roundingPolicyVersion": ROUNDING_POLICY_VERSION,
    }


@app.get("/ops", response_model=OpsResponse)
async def ops() -> OpsResponse:
    is_draining = bool(getattr(app.state, "is_draining", False))
    return OpsResponse(
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        status="degraded" if is_draining else "ok",
        checks=OpsChecks(live=True, ready=not is_draining, draining=is_draining),
        inputModes=list(SUPPORTED_INPUT_MODES),
    )


@app.get("/integration/capabilities", response_model=IntegrationCapabilitiesResponse)
async def integration_capabilities() -> IntegrationCapabilitiesResponse:
    return IntegrationCapabilitiesResponse(
        sourceService=SERVICE_NAME,
        policyVersion="risk.v1",
        supportedInputModes=list(SUPPORTED_INPUT_MODES),
        features=[CapabilityFeature(key=feature_key) for feature_key in CAPABILITY_FEATURE_KEYS],
        workflows=[
            CapabilityWorkflow(workflow_key=workflow_key)
            for workflow_key in CAPABILITY_WORKFLOW_KEYS
        ],
    )


@app.post(
    "/analytics/risk/concentration",
    response_model=ConcentrationResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate concentration risk analytics",
    description=(
        "Calculates concentration-risk HHI metrics from current and projected position "
        "weights. Returns current, proposed, and delta concentration."
    ),
)
async def analytics_risk_concentration(request: ConcentrationRequest) -> ConcentrationResponse:
    return calculate_concentration(request)


@app.post(
    "/analytics/risk/calculate",
    response_model=RiskResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate portfolio risk metrics",
    description=(
        "Calculates risk metrics from provided return series using stateless input mode. "
        "Supports EXPLICIT/YEAR/MTD/QTD/YTD/ONE_YEAR/THREE_YEAR/FIVE_YEAR/SI periods, "
        "all VaR methods (HISTORICAL/GAUSSIAN/CORNISH_FISHER), and benchmark-aware metrics."
    ),
)
async def analytics_risk_calculate(request: RiskCalculationRequest) -> RiskResponse:
    return calculate_risk(request)
