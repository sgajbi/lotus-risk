from fastapi import APIRouter, Request

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.drawdown import (
    DrawdownAnalyticsRequest,
    DrawdownInputMode,
    DrawdownResponse,
)
from app.dependencies.downstream_clients import resolve_lotus_performance_client
from app.dependencies.request_context import request_correlation_id
from app.openapi_examples import DRAWDOWN_EXAMPLES, request_body_examples
from app.services.drawdown_engine import calculate_drawdown
from app.services.drawdown_mode_adapter import calculate_drawdown_stateful
from app.services.endpoint_observation import observed_endpoint

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/drawdown",
    response_model=DrawdownResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="calculateDrawdownAnalytics",
    summary="Calculate realized drawdown analytics",
    openapi_extra=request_body_examples(DRAWDOWN_EXAMPLES),
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
        if stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")
        return await observed_endpoint(
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
        if stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")
        performance_client = resolve_lotus_performance_client(request)
        return await observed_endpoint(
            endpoint="drawdown",
            input_mode=input_mode,
            operation=lambda: calculate_drawdown_stateful(
                stateful_input,
                analysis_options=request_payload.analysis_options,
                performance_client=performance_client,
                correlation_id=request_correlation_id(request),
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/drawdown"
    )
