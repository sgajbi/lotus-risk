from fastapi import FastAPI, HTTPException, Response, status
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app.contracts.risk import RiskCalculationRequest, RiskResponse
from app.enterprise_readiness import (
    build_enterprise_audit_middleware,
    validate_enterprise_runtime_config,
)
from app.middleware.correlation import CorrelationIdMiddleware
from app.services.risk_engine import calculate_risk

SERVICE_NAME = "lotus-risk"
SERVICE_VERSION = "0.1.0"
ROUNDING_POLICY_VERSION = "v1"

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)
app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
validate_enterprise_runtime_config()
app.middleware("http")(build_enterprise_audit_middleware())
Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, str]:
    if bool(getattr(app.state, "is_draining", False)):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "draining"}
    return {"status": "ready"}


@app.get("/metadata")
async def metadata() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "roundingPolicyVersion": ROUNDING_POLICY_VERSION,
    }


@app.get("/integration/capabilities")
async def integration_capabilities() -> dict[str, object]:
    return {
        "sourceService": SERVICE_NAME,
        "policyVersion": "risk.v1",
        "supportedInputModes": ["api"],
        "features": [
            {"key": "risk.analytics.risk_analytics", "enabled": True},
            {"key": "risk.analytics.concentration", "enabled": True},
            {"key": "risk.analytics.metrics", "enabled": True},
        ],
        "workflows": [
            {"workflow_key": "risk_snapshot", "enabled": True},
            {"workflow_key": "concentration_risk", "enabled": True},
        ],
    }


class _RiskPosition(BaseModel):
    security_id: str = Field(alias="securityId")
    proposed_quantity: float | None = Field(default=None, alias="proposedQuantity")
    quantity: float | None = None


class _RiskProxyRequest(BaseModel):
    current_positions: list[_RiskPosition] = Field(default_factory=list, alias="currentPositions")
    projected_positions: list[_RiskPosition] = Field(
        default_factory=list, alias="projectedPositions"
    )


def _compute_hhi(values: list[float]) -> float:
    total = sum(abs(v) for v in values)
    if total <= 0:
        return 0.0
    weights = [abs(v) / total for v in values]
    return sum(w * w for w in weights) * 10000.0


def _build_concentration_response(request: _RiskProxyRequest) -> dict[str, object]:
    current_values = [
        p.quantity for p in request.current_positions if p.quantity is not None and p.quantity > 0
    ]
    projected_values = [
        p.proposed_quantity
        for p in request.projected_positions
        if p.proposed_quantity is not None and p.proposed_quantity > 0
    ]
    current_hhi = _compute_hhi(current_values)
    proposed_hhi = _compute_hhi(projected_values) if projected_values else current_hhi
    return {
        "sourceService": SERVICE_NAME,
        "riskProxy": {
            "hhiCurrent": round(current_hhi, 6),
            "hhiProposed": round(proposed_hhi, 6),
            "hhiDelta": round(proposed_hhi - current_hhi, 6),
        },
    }


@app.post(
    "/analytics/risk/concentration",
    summary="Calculate concentration risk analytics",
    description=(
        "Calculates concentration-risk HHI metrics from current and projected position "
        "weights. Returns current, proposed, and delta concentration."
    ),
)
async def analytics_risk_concentration(request: _RiskProxyRequest) -> dict[str, object]:
    return _build_concentration_response(request)


@app.post("/analytics/workbench/risk-proxy", include_in_schema=False)
async def workbench_risk_proxy(request: _RiskProxyRequest) -> dict[str, object]:
    return _build_concentration_response(request)


@app.post(
    "/analytics/risk/calculate",
    response_model=RiskResponse,
    summary="Calculate portfolio risk metrics",
    description=(
        "Calculates risk metrics from provided return series using stateless input mode. "
        "Supports EXPLICIT/YEAR/MTD/QTD/YTD/ONE_YEAR/THREE_YEAR/FIVE_YEAR/SI periods, "
        "all VaR methods (HISTORICAL/GAUSSIAN/CORNISH_FISHER), and benchmark-aware metrics."
    ),
)
async def analytics_risk_calculate(request: RiskCalculationRequest) -> RiskResponse:
    try:
        return calculate_risk(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
