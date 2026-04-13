from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts.capabilities import (
    CAPABILITY_FEATURE_KEYS,
    CapabilityFeature,
    CapabilityWorkflow,
    IntegrationCapabilitiesResponse,
    SupportedInputMode,
)
from app.contracts.attribution import (
    AttributionInputMode,
    HistoricalAttributionRequest,
    HistoricalAttributionResponse,
)
from app.contracts.concentration import ConcentrationRequest, ConcentrationResponse
from app.contracts.drawdown import (
    DrawdownAnalyticsRequest,
    DrawdownInputMode,
    DrawdownResponse,
)
from app.contracts.error import ErrorResponse
from app.contracts.ops import DependencyStatus, OpsChecks, OpsResponse
from app.contracts.rolling import (
    RollingAnalyticsRequest,
    RollingInputMode,
    RollingResponse,
)
from app.contracts.risk import RiskAnalyticsRequest, RiskInputMode, RiskResponse
from app.enterprise_readiness import (
    build_enterprise_audit_middleware,
    validate_enterprise_runtime_config,
)
from app.error_response import error_response
from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient
from app.middleware.correlation import CorrelationIdMiddleware
from app.ops_runtime import resolve_ops_status, resolve_readiness_status
from app.observability import observation_start, record_endpoint_execution
from app.services.concentration_engine import calculate_concentration
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_mode_adapter import calculate_historical_attribution_stateful
from app.services.drawdown_engine import calculate_drawdown
from app.services.drawdown_mode_adapter import calculate_drawdown_stateful
from app.services.rolling_engine import calculate_rolling_metrics
from app.services.rolling_mode_adapter import calculate_rolling_metrics_stateful
from app.services.risk_engine import calculate_risk
from app.services.risk_mode_adapter import calculate_risk_stateful
from app.upstream_errors import UpstreamServiceError

SERVICE_NAME = "lotus-risk"
SERVICE_VERSION = "0.1.0"
ROUNDING_POLICY_VERSION = "v1"
SUPPORTED_INPUT_MODES: tuple[SupportedInputMode, ...] = ("stateless", "stateful", "simulation")
ResponseT = TypeVar("ResponseT")

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
    dependencies: list[DependencyStatus] = Field(
        description="Dependency runtime states used to determine readiness.",
        json_schema_extra={
            "example": [
                {
                    "service": "lotus-performance",
                    "base_url": "http://performance.dev.lotus",
                    "status": "ok",
                    "detail": "configured",
                }
            ]
        },
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
    424: {
        "model": ErrorResponse,
        "description": "Dependency rejected the request or did not provide required data.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "FAILED_DEPENDENCY",
                        "message": "lotus-performance /integration/returns/series rejected request (404): missing benchmark assignment",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-performance",
                            "operation": "/integration/returns/series",
                            "upstream_status_code": 404,
                            "retryable": False,
                        },
                    }
                }
            }
        },
    },
    403: ERROR_RESPONSE_403,
    404: ERROR_RESPONSE_404,
    422: ERROR_RESPONSE_422,
    502: {
        "model": ErrorResponse,
        "description": "Dependency returned an invalid or failing upstream response.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "UPSTREAM_FAILURE",
                        "message": "lotus-performance /integration/returns/series failed (503): upstream failed",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-performance",
                            "operation": "/integration/returns/series",
                            "upstream_status_code": 503,
                            "retryable": True,
                        },
                    }
                }
            }
        },
    },
    503: {
        "model": ErrorResponse,
        "description": "Dependency is unavailable or service is draining.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "UPSTREAM_UNAVAILABLE",
                        "message": "lotus-core /integration/reference/risk-free-series unavailable: network down",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-core",
                            "operation": "/integration/reference/risk-free-series",
                            "retryable": True,
                        },
                    }
                }
            }
        },
    },
    504: {
        "model": ErrorResponse,
        "description": "Dependency request timed out.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "UPSTREAM_TIMEOUT",
                        "message": "lotus-core /integration/reference/risk-free-series timed out: request timed out",
                        "correlation_id": "corr-123",
                        "details": {
                            "service": "lotus-core",
                            "operation": "/integration/reference/risk-free-series",
                            "retryable": True,
                        },
                    }
                }
            }
        },
    },
    "default": ERROR_RESPONSE_DEFAULT,
}


def _default_error_code(status_code: int) -> str:
    if status_code == status.HTTP_404_NOT_FOUND:
        return "RESOURCE_NOT_FOUND"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "AUTHORIZATION_DENIED"
    if status_code == status.HTTP_413_CONTENT_TOO_LARGE:
        return "PAYLOAD_TOO_LARGE"
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        return "INVALID_REQUEST"
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "INVALID_INPUT"
    return "REQUEST_REJECTED"


async def _observed_endpoint(
    *,
    endpoint: str,
    input_mode: str,
    operation: Callable[[], ResponseT | Awaitable[ResponseT]],
) -> ResponseT:
    started_at = observation_start()
    try:
        result = operation()
        if isinstance(result, Awaitable):
            result = await result
    except Exception:
        record_endpoint_execution(
            endpoint=endpoint,
            input_mode=input_mode,
            outcome="failure",
            started_at=started_at,
        )
        raise
    record_endpoint_execution(
        endpoint=endpoint,
        input_mode=input_mode,
        outcome="success",
        started_at=started_at,
    )
    return cast(ResponseT, result)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
    return error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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


@app.exception_handler(UpstreamServiceError)
async def handle_upstream_service_error(request: Request, exc: UpstreamServiceError) -> Response:
    details = dict(exc.details)
    details["retryable"] = exc.retryable
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=details,
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
    status_code, readiness_status, dependencies = resolve_readiness_status(app)
    response.status_code = status_code
    return ReadinessResponse(
        status=readiness_status,
        dependencies=[
            DependencyStatus(
                service=dependency.service,
                base_url=dependency.base_url,
                status=dependency.status,
                detail=dependency.detail,
                category=dependency.category,
                issue_code=dependency.issue_code,
            )
            for dependency in dependencies
        ],
    )


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
    readiness_status_code, _, dependencies = resolve_readiness_status(app)
    ops_status, _ = resolve_ops_status(app)
    is_draining = bool(getattr(app.state, "is_draining", False))
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
        dependencies=[
            DependencyStatus(
                service=dependency.service,
                base_url=dependency.base_url,
                status=dependency.status,
                detail=dependency.detail,
                category=dependency.category,
                issue_code=dependency.issue_code,
            )
            for dependency in dependencies
        ],
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
            CapabilityWorkflow(
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
            CapabilityWorkflow(
                workflow_key="concentration_risk",
                endpoint_path="/analytics/risk/concentration",
                supported_input_modes=["stateless", "stateful", "simulation"],
                support_status="full",
                notes=[
                    "simulation is supported only for concentration risk",
                    "issuer concentration includes coverage diagnostics",
                ],
            ),
            CapabilityWorkflow(
                workflow_key="drawdown_analytics",
                endpoint_path="/analytics/risk/drawdown",
                supported_input_modes=["stateless", "stateful"],
                support_status="full",
                notes=["simulation is intentionally unsupported"],
            ),
            CapabilityWorkflow(
                workflow_key="rolling_risk_analytics",
                endpoint_path="/analytics/risk/rolling-metrics",
                supported_input_modes=["stateless", "stateful"],
                support_status="full",
                notes=[
                    "simulation is intentionally unsupported",
                    "stateful rolling Sharpe depends on risk-free series availability from lotus-core",
                ],
            ),
            CapabilityWorkflow(
                workflow_key="historical_risk_attribution",
                endpoint_path="/analytics/risk/historical-attribution",
                supported_input_modes=["stateless", "stateful"],
                support_status="partial",
                notes=[
                    "simulation is intentionally unsupported",
                    "stateful active-risk supports POSITION, SECTOR, and ASSET_CLASS",
                    "stateful active-risk ISSUER remains gated",
                    "attribution residual and reconciled_sum must be preserved with contributors",
                ],
            ),
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
    "/analytics/risk/historical-attribution",
    response_model=HistoricalAttributionResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate historical risk attribution analytics",
    tags=["risk-analytics"],
    description=(
        "Calculates historical risk and active-risk attribution decompositions with contributor-level "
        "component, marginal, and percent contributions plus reconciliation diagnostics. Supports "
        "stateless execution and approved stateful execution. Stateful ACTIVE_RISK currently supports "
        "POSITION, SECTOR, and ASSET_CLASS grouping dimensions; ISSUER is intentionally gated and "
        "CUSTOM grouping is not supported in stateful mode."
    ),
)
async def analytics_risk_historical_attribution(
    request_payload: HistoricalAttributionRequest,
    request: Request,
) -> HistoricalAttributionResponse:
    input_mode = request_payload.input_mode.value
    if request_payload.input_mode == AttributionInputMode.STATELESS:
        stateless_input = request_payload.stateless_input
        assert stateless_input is not None
        return await _observed_endpoint(
            endpoint="historical-attribution",
            input_mode=input_mode,
            operation=lambda: calculate_historical_attribution(
                stateless_input,
                input_mode=AttributionInputMode.STATELESS,
            ),
        )

    if request_payload.input_mode == AttributionInputMode.STATEFUL:
        stateful_input = request_payload.stateful_input
        assert stateful_input is not None
        performance_client = getattr(app.state, "lotus_performance_client", None)
        if performance_client is None:
            performance_client = LotusPerformanceClient()
        core_client = getattr(app.state, "lotus_core_client", None)
        if core_client is None:
            core_client = LotusCoreClient()
        return await _observed_endpoint(
            endpoint="historical-attribution",
            input_mode=input_mode,
            operation=lambda: calculate_historical_attribution_stateful(
                stateful_input,
                performance_client=performance_client,
                core_client=core_client,
                correlation_id=request.headers.get("X-Correlation-Id"),
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/historical-attribution"
    )


@app.post(
    "/analytics/risk/concentration",
    response_model=ConcentrationResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate concentration risk analytics",
    tags=["risk-analytics"],
    description=(
        "Calculates portfolio, single-position, and issuer concentration analytics across "
        "stateless, stateful, and simulation modes. Returns position-level HHI, top-position "
        "weight, top-N cumulative weight, issuer-level HHI, top-issuer weight, issuer coverage "
        "diagnostics, and top concentration drivers for current and proposed states."
    ),
)
async def analytics_risk_concentration(
    payload: ConcentrationRequest,
    request: Request,
) -> ConcentrationResponse:
    core_client = getattr(app.state, "lotus_core_client", None)
    if core_client is None:
        core_client = LotusCoreClient()
    return await _observed_endpoint(
        endpoint="concentration",
        input_mode=payload.input_mode.value,
        operation=lambda: calculate_concentration(
            payload,
            core_client=core_client,
            correlation_id=request.headers.get("X-Correlation-Id"),
            actor_id=request.headers.get("X-Actor-Id"),
        ),
    )


@app.post(
    "/analytics/risk/drawdown",
    response_model=DrawdownResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate realized drawdown analytics",
    tags=["risk-analytics"],
    description=(
        "Calculates realized drawdown analytics for stateless or stateful return histories, including "
        "max drawdown, episode diagnostics, time-under-water, ulcer index, drawdown-at-risk, and "
        "benchmark-relative drawdown timing. The response echoes applied analysis and benchmark policy "
        "settings so downstream consumers can interpret results without reconstructing the request."
    ),
)
async def analytics_risk_drawdown(
    request_payload: DrawdownAnalyticsRequest,
    request: Request,
) -> DrawdownResponse:
    input_mode = request_payload.input_mode.value
    if request_payload.input_mode == DrawdownInputMode.STATELESS:
        stateless_input = request_payload.stateless_input
        assert stateless_input is not None
        return await _observed_endpoint(
            endpoint="drawdown",
            input_mode=input_mode,
            operation=lambda: calculate_drawdown(
                stateless_input,
                input_mode=DrawdownInputMode.STATELESS,
                analysis_options=request_payload.analysis_options,
            ),
        )

    if request_payload.input_mode == DrawdownInputMode.STATEFUL:
        stateful_input = request_payload.stateful_input
        assert stateful_input is not None
        performance_client = getattr(app.state, "lotus_performance_client", None)
        if performance_client is None:
            performance_client = LotusPerformanceClient()
        return await _observed_endpoint(
            endpoint="drawdown",
            input_mode=input_mode,
            operation=lambda: calculate_drawdown_stateful(
                stateful_input,
                analysis_options=request_payload.analysis_options,
                performance_client=performance_client,
                correlation_id=request.headers.get("X-Correlation-Id"),
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/drawdown"
    )


@app.post(
    "/analytics/risk/rolling-metrics",
    response_model=RollingResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate rolling risk metrics",
    tags=["risk-analytics"],
    description=(
        "Calculates rolling-window historical risk diagnostics including volatility, Sharpe, beta, "
        "tracking error, information ratio, and rolling max drawdown. Supports stateless and "
        "stateful execution, explicit rolling window configuration, benchmark-aware metrics, and "
        "optional rolling time-series emission."
    ),
)
async def analytics_risk_rolling_metrics(
    request_payload: RollingAnalyticsRequest,
    request: Request,
) -> RollingResponse:
    input_mode = request_payload.input_mode.value
    if request_payload.input_mode == RollingInputMode.STATELESS:
        stateless_input = request_payload.stateless_input
        assert stateless_input is not None
        return await _observed_endpoint(
            endpoint="rolling-metrics",
            input_mode=input_mode,
            operation=lambda: calculate_rolling_metrics(
                stateless_input,
                input_mode=RollingInputMode.STATELESS,
            ),
        )

    if request_payload.input_mode == RollingInputMode.STATEFUL:
        stateful_input = request_payload.stateful_input
        assert stateful_input is not None
        performance_client = getattr(app.state, "lotus_performance_client", None)
        if performance_client is None:
            performance_client = LotusPerformanceClient()
        core_client = getattr(app.state, "lotus_core_client", None)
        if core_client is None:
            core_client = LotusCoreClient()
        return await _observed_endpoint(
            endpoint="rolling-metrics",
            input_mode=input_mode,
            operation=lambda: calculate_rolling_metrics_stateful(
                stateful_input,
                performance_client=performance_client,
                core_client=core_client,
                correlation_id=request.headers.get("X-Correlation-Id"),
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/rolling-metrics"
    )


@app.post(
    "/analytics/risk/calculate",
    response_model=RiskResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate portfolio risk metrics",
    tags=["risk-analytics"],
    description=(
        "Calculates risk metrics from provided return series using stateless or stateful input modes. "
        "Supports EXPLICIT/YEAR/MTD/QTD/YTD/ONE_YEAR/THREE_YEAR/FIVE_YEAR/SI periods, "
        "all VaR methods (HISTORICAL/GAUSSIAN/CORNISH_FISHER), and benchmark-aware metrics."
    ),
)
async def analytics_risk_calculate(
    request_payload: RiskAnalyticsRequest,
    request: Request,
) -> RiskResponse:
    input_mode = request_payload.input_mode.value
    if request_payload.input_mode == RiskInputMode.STATELESS:
        stateless_input = request_payload.stateless_input
        assert stateless_input is not None
        return await _observed_endpoint(
            endpoint="risk/calculate",
            input_mode=input_mode,
            operation=lambda: calculate_risk(stateless_input),
        )

    if request_payload.input_mode == RiskInputMode.STATEFUL:
        stateful_input = request_payload.stateful_input
        assert stateful_input is not None
        performance_client = getattr(app.state, "lotus_performance_client", None)
        if performance_client is None:
            performance_client = LotusPerformanceClient()
        return await _observed_endpoint(
            endpoint="risk/calculate",
            input_mode=input_mode,
            operation=lambda: calculate_risk_stateful(
                stateful_input,
                performance_client=performance_client,
                correlation_id=request.headers.get("X-Correlation-Id"),
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/calculate"
    )
