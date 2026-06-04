from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

from fastapi import FastAPI, Request, Response

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
from app.contracts.drawdown import (
    DrawdownAnalyticsRequest,
    DrawdownInputMode,
    DrawdownResponse,
)
from app.contracts.mandate_health import (
    MandateRiskHealthContextRequest,
    MandateRiskHealthContextResponse,
)
from app.contracts.rolling import (
    RollingAnalyticsRequest,
    RollingInputMode,
    RollingResponse,
)
from app.contracts.risk import RiskAnalyticsRequest, RiskInputMode, RiskResponse
from app.contracts.risk_event_cohort import (
    RiskEventAffectedCohortRequest,
    RiskEventAffectedCohortResponse,
)
from app.contracts.scenario import RegimeScenarioPackRequest, RegimeScenarioPackResponse
from app.enterprise_readiness import (
    build_enterprise_audit_middleware,
    validate_enterprise_runtime_config,
)
from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient
from app.middleware.correlation import CorrelationIdMiddleware
from app.observability import observation_start, record_endpoint_execution, record_http_request
from app.routers.operational import router as operational_router
from app.service_metadata import (
    SERVICE_NAME as _SERVICE_NAME,
    SERVICE_VERSION as _SERVICE_VERSION,
)
from app.services.concentration_engine import calculate_concentration
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_mode_adapter import calculate_historical_attribution_stateful
from app.services.drawdown_engine import calculate_drawdown
from app.services.drawdown_mode_adapter import calculate_drawdown_stateful
from app.services.mandate_health_context import evaluate_mandate_risk_health_context
from app.services.rolling_engine import calculate_rolling_metrics
from app.services.rolling_mode_adapter import calculate_rolling_metrics_stateful
from app.services.risk_engine import calculate_risk
from app.services.risk_event_cohort_engine import evaluate_risk_event_affected_cohort
from app.services.risk_mode_adapter import calculate_risk_stateful
from app.services.scenario_engine import evaluate_regime_scenario_pack

ResponseT = TypeVar("ResponseT")
SERVICE_NAME: str = _SERVICE_NAME
SERVICE_VERSION: str = _SERVICE_VERSION

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)
app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
validate_enterprise_runtime_config()
app.middleware("http")(build_enterprise_audit_middleware())
register_exception_handlers(app)
app.include_router(operational_router)


@app.middleware("http")
async def observe_http_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    try:
        response = await call_next(request)
    except Exception:
        route = request.scope.get("route")
        handler = getattr(route, "path", request.url.path)
        record_http_request(handler=handler, method=request.method, status_code=500)
        raise
    route = request.scope.get("route")
    handler = getattr(route, "path", request.url.path)
    record_http_request(handler=handler, method=request.method, status_code=response.status_code)
    return response


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


@app.post(
    "/analytics/risk/mandate-health-context",
    response_model=MandateRiskHealthContextResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Evaluate source-owned mandate risk health context",
    tags=["risk-analytics"],
    description=(
        "Evaluates a bounded mandate risk health context using lotus-risk source-owned "
        "tracking-error methodology. The response preserves threshold posture, lineage, "
        "methodology ownership, and reason codes for downstream consumers such as lotus-manage "
        "without creating mandate actions, rebalance waves, client communications, or execution."
    ),
)
async def analytics_risk_mandate_health_context(
    request_payload: MandateRiskHealthContextRequest,
) -> MandateRiskHealthContextResponse:
    return await _observed_endpoint(
        endpoint="mandate-risk-health-context",
        input_mode="stateless",
        operation=lambda: evaluate_mandate_risk_health_context(request_payload),
    )


@app.post(
    "/analytics/risk/regime-scenario-pack/evaluate",
    response_model=RegimeScenarioPackResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Evaluate a governed regime scenario pack",
    tags=["risk-analytics"],
    description=(
        "Evaluates caller-supplied portfolio exposure weights against a governed CIO regime "
        "scenario pack and returns source-owned worst-case loss, policy-threshold breach posture, "
        "optional per-security contribution rows, CIO approval/effective-period/applicability "
        "posture, bounded reason codes, and lineage metadata. "
        "Consumers must not reconstruct scenario methodology outside lotus-risk."
    ),
)
async def analytics_risk_regime_scenario_pack(
    request_payload: RegimeScenarioPackRequest,
) -> RegimeScenarioPackResponse:
    return await _observed_endpoint(
        endpoint="regime-scenario-pack",
        input_mode="stateless",
        operation=lambda: evaluate_regime_scenario_pack(request_payload),
    )


@app.post(
    "/analytics/risk/risk-event-cohorts/evaluate",
    response_model=RiskEventAffectedCohortResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Evaluate a governed risk-event affected cohort",
    tags=["risk-analytics"],
    description=(
        "Evaluates candidate portfolios against governed risk-event definitions and returns "
        "source-owned affected-cohort membership, impact scores, exclusions, lineage source refs, "
        "bounded reason codes, and supportability posture. Consumers must not reconstruct "
        "risk-event cohort membership outside lotus-risk, and this endpoint does not create "
        "rebalance waves, approvals, or campaign workflow."
    ),
)
async def analytics_risk_event_affected_cohort(
    request_payload: RiskEventAffectedCohortRequest,
) -> RiskEventAffectedCohortResponse:
    return await _observed_endpoint(
        endpoint="risk-event-cohort",
        input_mode="stateless",
        operation=lambda: evaluate_risk_event_affected_cohort(request_payload),
    )


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
                include_benchmark=request_payload.benchmark_policy.include_benchmark,
                missing_benchmark_policy=request_payload.benchmark_policy.missing_benchmark_policy,
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
        "Supports EXPLICIT/YEAR/MTD/QTD/YTD/1Y/3Y/5Y/SI periods, with legacy "
        "ONE_YEAR/THREE_YEAR/FIVE_YEAR aliases normalized at the boundary. "
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
