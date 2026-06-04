from fastapi import APIRouter, Request

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.concentration import ConcentrationRequest, ConcentrationResponse
from app.dependencies.downstream_clients import resolve_lotus_core_client
from app.dependencies.request_context import request_actor_id, request_correlation_id
from app.services.concentration_engine import calculate_concentration
from app.services.endpoint_observation import observed_endpoint

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/concentration",
    response_model=ConcentrationResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="calculateConcentrationRiskAnalytics",
    summary="Calculate concentration risk analytics",
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
    core_client = resolve_lotus_core_client(request)
    return await observed_endpoint(
        endpoint="concentration",
        input_mode=payload.input_mode.value,
        operation=lambda: calculate_concentration(
            payload,
            core_client=core_client,
            correlation_id=request_correlation_id(request),
            actor_id=request_actor_id(request),
        ),
    )
