from typing import Annotated

from fastapi import APIRouter, Depends

from app.api_errors import STATEFUL_TENANT_ERROR_RESPONSES
from app.contracts.downstream_authority import admit_downstream_authority
from app.contracts.risk import RiskAnalyticsRequest, RiskInputMode, RiskResponse
from app.dependencies.request_context import request_correlation_id, request_tenant_id
from app.openapi_examples import RISK_CALCULATE_EXAMPLES, stateful_request_openapi_extra
from app.runtime.downstream_clients import RuntimeDownstreamClients, runtime_downstream_clients
from app.services.endpoint_observation import observed_endpoint
from app.services.risk_engine import calculate_risk
from app.services.risk_mode_adapter import calculate_risk_stateful

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/calculate",
    response_model=RiskResponse,
    responses=STATEFUL_TENANT_ERROR_RESPONSES,
    operation_id="calculateRiskAnalytics",
    summary="Calculate portfolio risk metrics",
    openapi_extra=stateful_request_openapi_extra(RISK_CALCULATE_EXAMPLES),
    description=(
        "Calculates risk metrics from provided return series using stateless or stateful input modes. "
        "Supports EXPLICIT/YEAR/MTD/QTD/YTD/1Y/3Y/5Y/SI periods, with legacy "
        "ONE_YEAR/THREE_YEAR/FIVE_YEAR aliases normalized at the boundary. "
        "all VaR methods (HISTORICAL/GAUSSIAN/CORNISH_FISHER), and benchmark-aware metrics."
    ),
)
async def analytics_risk_calculate(
    request_payload: RiskAnalyticsRequest,
    runtime_clients: Annotated[RuntimeDownstreamClients, Depends(runtime_downstream_clients)],
    correlation_id: Annotated[str | None, Depends(request_correlation_id)],
    tenant_id: Annotated[str | None, Depends(request_tenant_id)],
) -> RiskResponse:
    input_mode = request_payload.input_mode.value
    if request_payload.input_mode == RiskInputMode.STATELESS:
        stateless_input = request_payload.stateless_input
        if stateless_input is None:
            raise ValueError("stateless_input is required when input_mode=stateless")
        return await observed_endpoint(
            endpoint="risk/calculate",
            input_mode=input_mode,
            response_model=RiskResponse,
            operation=lambda: calculate_risk(stateless_input),
        )

    if request_payload.input_mode == RiskInputMode.STATEFUL:
        stateful_input = request_payload.stateful_input
        if stateful_input is None:
            raise ValueError("stateful_input is required when input_mode=stateful")
        # Admission precedes the observed operation: a refused request makes no
        # upstream call and, like other request refusals, is not an endpoint execution.
        authority = admit_downstream_authority(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        return await observed_endpoint(
            endpoint="risk/calculate",
            input_mode=input_mode,
            response_model=RiskResponse,
            operation=lambda: calculate_risk_stateful(
                stateful_input,
                performance_client=runtime_clients.lotus_performance(),
                core_client=(
                    runtime_clients.lotus_core() if "SHARPE" in stateful_input.metrics else None
                ),
                authority=authority,
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/calculate"
    )
