from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.api_errors import STATEFUL_TENANT_ERROR_RESPONSES
from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationRequest,
    ConcentrationResponse,
)
from app.contracts.downstream_authority import (
    DownstreamAuthority,
    admit_downstream_authority,
)
from app.dependencies.request_context import (
    request_actor_id,
    request_correlation_id,
    request_tenant_id,
)
from app.openapi_examples import CONCENTRATION_EXAMPLES, stateful_request_openapi_extra
from app.runtime.downstream_clients import RuntimeDownstreamClients, runtime_downstream_clients
from app.services.concentration_engine import calculate_concentration
from app.services.endpoint_observation import observed_endpoint

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/concentration",
    response_model=ConcentrationResponse,
    responses=STATEFUL_TENANT_ERROR_RESPONSES,
    operation_id="calculateConcentrationRiskAnalytics",
    summary="Calculate concentration risk analytics",
    openapi_extra=stateful_request_openapi_extra(CONCENTRATION_EXAMPLES),
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
    tenant_id: Annotated[str | None, Depends(request_tenant_id)],
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
    # Stateless concentration keeps working without tenant authority; stateful and
    # simulation modes admit it here, before the observed operation, so a refused
    # request makes no upstream call and is not an endpoint execution.
    authority: DownstreamAuthority | None = None
    if payload.input_mode != ConcentrationInputMode.STATELESS:
        authority = admit_downstream_authority(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
    return await observed_endpoint(
        endpoint="concentration",
        input_mode=payload.input_mode.value,
        response_model=ConcentrationResponse,
        operation=lambda: calculate_concentration(
            payload,
            authority=authority,
            core_client=(
                runtime_clients.lotus_core_optional()
                if payload.input_mode == ConcentrationInputMode.STATELESS
                else runtime_clients.lotus_core()
            ),
            correlation_id=correlation_id,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
        ),
    )
