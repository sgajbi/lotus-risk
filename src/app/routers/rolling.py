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
from app.services.endpoint_observation import observed_endpoint
from app.services.rolling_engine import calculate_rolling_metrics
from app.services.rolling_mode_adapter import calculate_rolling_metrics_stateful

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/rolling-metrics",
    response_model=RollingResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate rolling risk metrics",
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
        return await observed_endpoint(
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
        performance_client = resolve_lotus_performance_client(request)
        core_client = resolve_lotus_core_client(request)
        return await observed_endpoint(
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
