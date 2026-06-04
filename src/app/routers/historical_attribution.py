from fastapi import APIRouter, Request

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.attribution import (
    AttributionInputMode,
    HistoricalAttributionRequest,
    HistoricalAttributionResponse,
)
from app.dependencies.downstream_clients import (
    resolve_lotus_core_client,
    resolve_lotus_performance_client,
)
from app.dependencies.request_context import request_correlation_id
from app.openapi_examples import HISTORICAL_ATTRIBUTION_EXAMPLES, request_body_examples
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
        performance_client = resolve_lotus_performance_client(request)
        core_client = resolve_lotus_core_client(request)
        return await observed_endpoint(
            endpoint="historical-attribution",
            input_mode=input_mode,
            operation=lambda: calculate_historical_attribution_stateful(
                stateful_input,
                performance_client=performance_client,
                core_client=core_client,
                correlation_id=request_correlation_id(request),
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/historical-attribution"
    )
