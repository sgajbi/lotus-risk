from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.concentration import ConcentrationRequest, ConcentrationResponse
from app.dependencies.request_context import request_actor_id, request_correlation_id
from app.openapi_examples import CONCENTRATION_EXAMPLES, request_body_examples
from app.runtime.downstream_clients import RuntimeDownstreamClients, runtime_downstream_clients
from app.services.concentration_engine import calculate_concentration
from app.services.endpoint_observation import observed_endpoint

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/concentration",
    response_model=ConcentrationResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="calculateConcentrationRiskAnalytics",
    summary="Calculate concentration risk analytics",
    openapi_extra=request_body_examples(CONCENTRATION_EXAMPLES),
    description=(
        "Calculates portfolio, single-position, and issuer concentration analytics across "
        "stateless, stateful, and simulation modes. Returns position-level HHI, top-position "
        "weight, top-N cumulative weight, issuer-level HHI, top-issuer weight, issuer coverage "
        "diagnostics, and top concentration drivers for current and proposed states."
    ),
)
async def analytics_risk_concentration(
    payload: ConcentrationRequest,
    runtime_clients: Annotated[RuntimeDownstreamClients, Depends(runtime_downstream_clients)],
    correlation_id: Annotated[str | None, Depends(request_correlation_id)],
    actor_id: Annotated[str | None, Depends(request_actor_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            description=(
                "Required when simulation_input.simulation_changes is non-empty. "
                "Forwarded to lotus-core with a deterministic change-set fingerprint for "
                "simulation replay/conflict enforcement."
            ),
        ),
    ] = None,
) -> ConcentrationResponse:
    return await observed_endpoint(
        endpoint="concentration",
        input_mode=payload.input_mode.value,
        response_model=ConcentrationResponse,
        operation=lambda: calculate_concentration(
            payload,
            core_client=runtime_clients.lotus_core(),
            correlation_id=correlation_id,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
        ),
    )
