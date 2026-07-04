from typing import Annotated

from fastapi import APIRouter, Depends

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.attribution import (
    AttributionInputMode,
    HistoricalAttributionRequest,
    HistoricalAttributionResponse,
)
from app.dependencies.request_context import request_correlation_id
from app.openapi_examples import HISTORICAL_ATTRIBUTION_EXAMPLES, request_body_examples
from app.runtime.downstream_clients import RuntimeDownstreamClients, runtime_downstream_clients
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_mode_adapter import calculate_historical_attribution_stateful
from app.services.endpoint_observation import observed_endpoint

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/historical-attribution",
    response_model=HistoricalAttributionResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="calculateHistoricalRiskAttribution",
    summary="Calculate historical risk attribution analytics",
    openapi_extra=request_body_examples(HISTORICAL_ATTRIBUTION_EXAMPLES),
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
    runtime_clients: Annotated[RuntimeDownstreamClients, Depends(runtime_downstream_clients)],
    correlation_id: Annotated[str | None, Depends(request_correlation_id)],
) -> HistoricalAttributionResponse:
    if request_payload.input_mode == AttributionInputMode.STATELESS:
        return await _stateless_historical_attribution_response(request_payload)

    if request_payload.input_mode == AttributionInputMode.STATEFUL:
        return await _stateful_historical_attribution_response(
            request_payload=request_payload,
            runtime_clients=runtime_clients,
            correlation_id=correlation_id,
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/historical-attribution"
    )


async def _stateless_historical_attribution_response(
    request_payload: HistoricalAttributionRequest,
) -> HistoricalAttributionResponse:
    stateless_input = request_payload.stateless_input
    if stateless_input is None:
        raise ValueError("stateless_input is required when input_mode=stateless")
    return await observed_endpoint(
        endpoint="historical-attribution",
        input_mode=request_payload.input_mode.value,
        operation=lambda: calculate_historical_attribution(
            stateless_input,
            input_mode=AttributionInputMode.STATELESS,
        ),
    )


async def _stateful_historical_attribution_response(
    *,
    request_payload: HistoricalAttributionRequest,
    runtime_clients: RuntimeDownstreamClients,
    correlation_id: str | None,
) -> HistoricalAttributionResponse:
    stateful_input = request_payload.stateful_input
    if stateful_input is None:
        raise ValueError("stateful_input is required when input_mode=stateful")
    return await observed_endpoint(
        endpoint="historical-attribution",
        input_mode=request_payload.input_mode.value,
        operation=lambda: calculate_historical_attribution_stateful(
            stateful_input,
            performance_client=runtime_clients.lotus_performance(),
            core_client=runtime_clients.lotus_core(),
            correlation_id=correlation_id,
        ),
    )
