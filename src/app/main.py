from fastapi import FastAPI, Request

from app.api_errors import (
    STANDARD_ERROR_RESPONSES,
    register_exception_handlers,
)
from app.contracts.attribution import (
    AttributionInputMode,
    HistoricalAttributionRequest,
    HistoricalAttributionResponse,
)
from app.contracts.concentration import ConcentrationRequest, ConcentrationResponse
from app.enterprise_readiness import (
    build_enterprise_audit_middleware,
    validate_enterprise_runtime_config,
)
from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.http_observation import build_http_observation_middleware
from app.routers.drawdown import router as drawdown_router
from app.routers.operational import router as operational_router
from app.routers.risk_calculation import router as risk_calculation_router
from app.routers.rolling import router as rolling_router
from app.routers.source_products import router as source_products_router
from app.service_metadata import (
    SERVICE_NAME as _SERVICE_NAME,
    SERVICE_VERSION as _SERVICE_VERSION,
)
from app.services.concentration_engine import calculate_concentration
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_mode_adapter import calculate_historical_attribution_stateful
from app.services.endpoint_observation import observed_endpoint

SERVICE_NAME: str = _SERVICE_NAME
SERVICE_VERSION: str = _SERVICE_VERSION

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)
app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
validate_enterprise_runtime_config()
app.middleware("http")(build_enterprise_audit_middleware())
app.middleware("http")(build_http_observation_middleware())
register_exception_handlers(app)
app.include_router(operational_router)
app.include_router(source_products_router)
app.include_router(risk_calculation_router)
app.include_router(drawdown_router)
app.include_router(rolling_router)


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
        "POSITION, SECTOR, ASSET_CLASS, and ISSUER grouping dimensions through lotus-performance "
        "benchmark exposure context. CUSTOM grouping is not supported in stateful mode."
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
        return await observed_endpoint(
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
        return await observed_endpoint(
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
    return await observed_endpoint(
        endpoint="concentration",
        input_mode=payload.input_mode.value,
        operation=lambda: calculate_concentration(
            payload,
            core_client=core_client,
            correlation_id=request.headers.get("X-Correlation-Id"),
            actor_id=request.headers.get("X-Actor-Id"),
        ),
    )
