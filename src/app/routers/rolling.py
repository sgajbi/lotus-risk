from fastapi import APIRouter, Request

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.rolling import (
    RollingAnalyticsRequest,
    RollingInputMode,
    RollingResponse,
)
from app.dependencies.downstream_clients import (
    resolve_lotus_core_client,
    resolve_lotus_performance_client,
)
from app.dependencies.request_context import request_correlation_id
from app.openapi_examples import ROLLING_METRICS_EXAMPLES, request_body_examples
from app.services.endpoint_observation import observed_endpoint
from app.services.rolling_engine import calculate_rolling_metrics
from app.services.rolling_mode_adapter import calculate_rolling_metrics_stateful

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/rolling-metrics",
    response_model=RollingResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="calculateRollingRiskMetrics",
    summary="Calculate rolling risk metrics",
    openapi_extra=request_body_examples(ROLLING_METRICS_EXAMPLES),
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
    if request_payload.input_mode == RollingInputMode.STATELESS:
        return await _stateless_rolling_response(request_payload)

    if request_payload.input_mode == RollingInputMode.STATEFUL:
        return await _stateful_rolling_response(
            request_payload=request_payload,
            request=request,
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/rolling-metrics"
    )


async def _stateless_rolling_response(
    request_payload: RollingAnalyticsRequest,
) -> RollingResponse:
    stateless_input = request_payload.stateless_input
    if stateless_input is None:
        raise ValueError("stateless_input is required when input_mode=stateless")
    return await observed_endpoint(
        endpoint="rolling-metrics",
        input_mode=request_payload.input_mode.value,
        operation=lambda: calculate_rolling_metrics(
            stateless_input,
            input_mode=RollingInputMode.STATELESS,
        ),
    )


async def _stateful_rolling_response(
    *,
    request_payload: RollingAnalyticsRequest,
    request: Request,
) -> RollingResponse:
    stateful_input = request_payload.stateful_input
    if stateful_input is None:
        raise ValueError("stateful_input is required when input_mode=stateful")
    performance_client = resolve_lotus_performance_client(request)
    core_client = resolve_lotus_core_client(request)
    return await observed_endpoint(
        endpoint="rolling-metrics",
        input_mode=request_payload.input_mode.value,
        operation=lambda: calculate_rolling_metrics_stateful(
            stateful_input,
            performance_client=performance_client,
            core_client=core_client,
            correlation_id=request_correlation_id(request),
        ),
    )
