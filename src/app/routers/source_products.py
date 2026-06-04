from fastapi import APIRouter

from app.api_errors import STANDARD_ERROR_RESPONSES
from app.contracts.mandate_health import (
    MandateRiskHealthContextRequest,
    MandateRiskHealthContextResponse,
)
from app.contracts.risk_event_cohort import (
    RiskEventAffectedCohortRequest,
    RiskEventAffectedCohortResponse,
)
from app.contracts.scenario import RegimeScenarioPackRequest, RegimeScenarioPackResponse
from app.services.endpoint_observation import observed_endpoint
from app.services.mandate_health_context import evaluate_mandate_risk_health_context
from app.services.risk_event_cohort_engine import evaluate_risk_event_affected_cohort
from app.services.scenario_engine import evaluate_regime_scenario_pack

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/mandate-health-context",
    response_model=MandateRiskHealthContextResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="evaluateMandateRiskHealthContext",
    summary="Evaluate source-owned mandate risk health context",
    description=(
        "Evaluates a bounded mandate risk health context using lotus-risk source-owned "
        "tracking-error methodology. The response preserves threshold posture, lineage, "
        "methodology ownership, and reason codes for downstream consumers such as lotus-manage "
        "without creating mandate actions, rebalance waves, client communications, or execution."
    ),
)
async def analytics_risk_mandate_health_context(
    request_payload: MandateRiskHealthContextRequest,
) -> MandateRiskHealthContextResponse:
    return await observed_endpoint(
        endpoint="mandate-risk-health-context",
        input_mode="stateless",
        operation=lambda: evaluate_mandate_risk_health_context(request_payload),
    )


@router.post(
    "/analytics/risk/regime-scenario-pack/evaluate",
    response_model=RegimeScenarioPackResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="evaluateRegimeScenarioPack",
    summary="Evaluate a governed regime scenario pack",
    description=(
        "Evaluates caller-supplied portfolio exposure weights against a governed CIO regime "
        "scenario pack and returns source-owned worst-case loss, policy-threshold breach posture, "
        "optional per-security contribution rows, CIO approval/effective-period/applicability "
        "posture, bounded reason codes, and lineage metadata. "
        "Consumers must not reconstruct scenario methodology outside lotus-risk."
    ),
)
async def analytics_risk_regime_scenario_pack(
    request_payload: RegimeScenarioPackRequest,
) -> RegimeScenarioPackResponse:
    return await observed_endpoint(
        endpoint="regime-scenario-pack",
        input_mode="stateless",
        operation=lambda: evaluate_regime_scenario_pack(request_payload),
    )


@router.post(
    "/analytics/risk/risk-event-cohorts/evaluate",
    response_model=RiskEventAffectedCohortResponse,
    responses=STANDARD_ERROR_RESPONSES,
    operation_id="evaluateRiskEventAffectedCohort",
    summary="Evaluate a governed risk-event affected cohort",
    description=(
        "Evaluates candidate portfolios against governed risk-event definitions and returns "
        "source-owned affected-cohort membership, impact scores, exclusions, lineage source refs, "
        "bounded reason codes, and supportability posture. Consumers must not reconstruct "
        "risk-event cohort membership outside lotus-risk, and this endpoint does not create "
        "rebalance waves, approvals, or campaign workflow."
    ),
)
async def analytics_risk_event_affected_cohort(
    request_payload: RiskEventAffectedCohortRequest,
) -> RiskEventAffectedCohortResponse:
    return await observed_endpoint(
        endpoint="risk-event-cohort",
        input_mode="stateless",
        operation=lambda: evaluate_risk_event_affected_cohort(request_payload),
    )
