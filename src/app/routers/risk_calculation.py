from fastapi import APIRouter, Request

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.risk import RiskAnalyticsRequest, RiskInputMode, RiskResponse
from app.integrations.lotus_performance_client import LotusPerformanceClient
from app.services.endpoint_observation import observed_endpoint
from app.services.risk_engine import calculate_risk
from app.services.risk_mode_adapter import calculate_risk_stateful

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/calculate",
    response_model=RiskResponse,
    responses=STANDARD_ERROR_RESPONSES,
    summary="Calculate portfolio risk metrics",
    description=(
        "Calculates risk metrics from provided return series using stateless or stateful input modes. "
        "Supports EXPLICIT/YEAR/MTD/QTD/YTD/1Y/3Y/5Y/SI periods, with legacy "
        "ONE_YEAR/THREE_YEAR/FIVE_YEAR aliases normalized at the boundary. "
        "all VaR methods (HISTORICAL/GAUSSIAN/CORNISH_FISHER), and benchmark-aware metrics."
    ),
)
async def analytics_risk_calculate(
    request_payload: RiskAnalyticsRequest,
    request: Request,
) -> RiskResponse:
    input_mode = request_payload.input_mode.value
    if request_payload.input_mode == RiskInputMode.STATELESS:
        stateless_input = request_payload.stateless_input
        assert stateless_input is not None
        return await observed_endpoint(
            endpoint="risk/calculate",
            input_mode=input_mode,
            operation=lambda: calculate_risk(stateless_input),
        )

    if request_payload.input_mode == RiskInputMode.STATEFUL:
        stateful_input = request_payload.stateful_input
        assert stateful_input is not None
        performance_client = getattr(request.app.state, "lotus_performance_client", None)
        if performance_client is None:
            performance_client = LotusPerformanceClient()
        return await observed_endpoint(
            endpoint="risk/calculate",
            input_mode=input_mode,
            operation=lambda: calculate_risk_stateful(
                stateful_input,
                performance_client=performance_client,
                correlation_id=request.headers.get("X-Correlation-Id"),
            ),
        )

    raise ValueError(
        f"Unsupported input_mode={request_payload.input_mode.value} for /analytics/risk/calculate"
    )
