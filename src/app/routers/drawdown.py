from typing import Annotated

from fastapi import APIRouter, Depends

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.drawdown import (
    DrawdownAnalyticsRequest,
    DrawdownInputMode,
    DrawdownResponse,
)
from app.dependencies.request_context import request_correlation_id
from app.openapi_examples import DRAWDOWN_EXAMPLES, request_body_examples
from app.runtime.downstream_clients import RuntimeDownstreamClients, runtime_downstream_clients
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
    runtime_clients: Annotated[RuntimeDownstreamClients, Depends(runtime_downstream_clients)],
    correlation_id: Annotated[str | None, Depends(request_correlation_id)],
) -> DrawdownResponse:
    if request_payload.input_mode == DrawdownInputMode.STATELESS:
        return await _stateless_drawdown_response(request_payload)

    if request_payload.input_mode == DrawdownInputMode.STATEFUL:
        return await _stateful_drawdown_response(
            request_payload=request_payload,
            runtime_clients=runtime_clients,
            correlation_id=correlation_id,
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/drawdown"
    )


async def _stateless_drawdown_response(
    request_payload: DrawdownAnalyticsRequest,
) -> DrawdownResponse:
    stateless_input = request_payload.stateless_input
    if stateless_input is None:
        raise ValueError("stateless_input is required when input_mode=stateless")
    return await observed_endpoint(
        endpoint="drawdown",
        input_mode=request_payload.input_mode.value,
        operation=lambda: calculate_drawdown(
            stateless_input,
            input_mode=DrawdownInputMode.STATELESS,
            analysis_options=request_payload.analysis_options,
            include_benchmark=request_payload.benchmark_policy.include_benchmark,
            missing_benchmark_policy=request_payload.benchmark_policy.missing_benchmark_policy,
        ),
    )


async def _stateful_drawdown_response(
    *,
    request_payload: DrawdownAnalyticsRequest,
    runtime_clients: RuntimeDownstreamClients,
    correlation_id: str | None,
) -> DrawdownResponse:
    stateful_input = request_payload.stateful_input
    if stateful_input is None:
        raise ValueError("stateful_input is required when input_mode=stateful")
    return await observed_endpoint(
        endpoint="drawdown",
        input_mode=request_payload.input_mode.value,
        operation=lambda: calculate_drawdown_stateful(
            stateful_input,
            analysis_options=request_payload.analysis_options,
            performance_client=runtime_clients.lotus_performance(),
            correlation_id=correlation_id,
        ),
    )
