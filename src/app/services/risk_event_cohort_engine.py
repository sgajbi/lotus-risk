from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.contracts.risk_event_cohort import (
    RiskEventAffectedCohortRequest,
    RiskEventAffectedCohortResponse,
    RiskEventAffectedPortfolio,
    RiskEventCohortMetadata,
    RiskEventCohortSupportabilityState,
    RiskEventExcludedPortfolio,
    RiskEventPortfolioExposure,
)


@dataclass(frozen=True)
class RiskEventDefinition:
    risk_event_id: str
    display_name: str
    shock_by_bucket: dict[str, float]


@dataclass(frozen=True)
class _PortfolioRiskEventEvaluation:
    portfolio: RiskEventPortfolioExposure
    impact_score: float
    dominant_bucket: str
    bucket_impacts: dict[str, float]
    unsupported_buckets: list[str]


RISK_EVENTS: dict[str, RiskEventDefinition] = {
    "RISK_EVENT_2026_Q2_RATES_UP": RiskEventDefinition(
        risk_event_id="RISK_EVENT_2026_Q2_RATES_UP",
        display_name="Rates-up inflation persistence",
        shock_by_bucket={
            "EQUITY": -0.04,
            "FIXED_INCOME": -0.15,
            "ALTERNATIVES": -0.03,
            "CASH": 0.0,
        },
    ),
    "RISK_EVENT_2026_Q2_RISK_OFF": RiskEventDefinition(
        risk_event_id="RISK_EVENT_2026_Q2_RISK_OFF",
        display_name="Risk-off liquidity stress",
        shock_by_bucket={
            "EQUITY": -0.18,
            "FIXED_INCOME": -0.02,
            "ALTERNATIVES": -0.10,
            "CASH": 0.0,
        },
    ),
}


def evaluate_risk_event_affected_cohort(
    request: RiskEventAffectedCohortRequest,
) -> RiskEventAffectedCohortResponse:
    risk_event = RISK_EVENTS.get(request.risk_event_id)
    if risk_event is None:
        raise ValueError(f"Unsupported risk_event_id: {request.risk_event_id}")

    affected: list[RiskEventAffectedPortfolio] = []
    excluded: list[RiskEventExcludedPortfolio] = []
    supported_buckets = set(risk_event.shock_by_bucket)

    for portfolio in request.portfolios:
        evaluation = _evaluate_portfolio_exposure(
            portfolio=portfolio,
            risk_event=risk_event,
            supported_buckets=supported_buckets,
        )
        if _is_affected(evaluation, minimum_impact_score=request.minimum_impact_score):
            affected.append(_affected_portfolio(request=request, evaluation=evaluation))
            continue
        excluded.append(_excluded_portfolio(evaluation))

    request_fingerprint = _request_fingerprint(request)
    supportability, reason_codes = _supportability_state(
        affected=affected,
        excluded=excluded,
    )
    return RiskEventAffectedCohortResponse(
        cohort_id=_cohort_id(request_fingerprint),
        risk_event_id=request.risk_event_id,
        display_name=risk_event.display_name,
        as_of_date=request.as_of_date,
        affected_portfolios=affected,
        excluded_portfolios=excluded,
        reason_codes=sorted(set(reason_codes)),
        metadata=RiskEventCohortMetadata(
            request_fingerprint=request_fingerprint,
            calculation_supportability=supportability,
        ),
    )


def _evaluate_portfolio_exposure(
    *,
    portfolio: RiskEventPortfolioExposure,
    risk_event: RiskEventDefinition,
    supported_buckets: set[str],
) -> _PortfolioRiskEventEvaluation:
    normalized_exposures = {
        bucket.upper(): weight for bucket, weight in portfolio.exposure_weights.items()
    }
    unsupported_buckets = sorted(set(normalized_exposures) - supported_buckets)
    bucket_impacts = {
        bucket: round(weight * risk_event.shock_by_bucket.get(bucket, 0.0), 6)
        for bucket, weight in normalized_exposures.items()
    }
    impact_score = round(sum(abs(value) for value in bucket_impacts.values()), 6)
    dominant_bucket = max(
        bucket_impacts,
        key=lambda bucket: abs(bucket_impacts[bucket]),
        default="UNKNOWN",
    )
    return _PortfolioRiskEventEvaluation(
        portfolio=portfolio,
        impact_score=impact_score,
        dominant_bucket=dominant_bucket,
        bucket_impacts=bucket_impacts,
        unsupported_buckets=unsupported_buckets,
    )


def _is_affected(
    evaluation: _PortfolioRiskEventEvaluation,
    *,
    minimum_impact_score: float,
) -> bool:
    return evaluation.impact_score >= minimum_impact_score and not evaluation.unsupported_buckets


def _affected_portfolio(
    *,
    request: RiskEventAffectedCohortRequest,
    evaluation: _PortfolioRiskEventEvaluation,
) -> RiskEventAffectedPortfolio:
    portfolio = evaluation.portfolio
    return RiskEventAffectedPortfolio(
        portfolio_id=portfolio.portfolio_id,
        mandate_id=portfolio.mandate_id,
        portfolio_manager_id=portfolio.portfolio_manager_id,
        impact_score=evaluation.impact_score,
        dominant_bucket=evaluation.dominant_bucket,
        bucket_impacts=evaluation.bucket_impacts,
        source_ref=(
            "risk-event-cohort:"
            f"{request.risk_event_id}:{request.as_of_date.isoformat()}:"
            f"{portfolio.portfolio_id}"
        ),
        reason_codes=["RISK_EVENT_THRESHOLD_BREACHED"],
    )


def _excluded_portfolio(
    evaluation: _PortfolioRiskEventEvaluation,
) -> RiskEventExcludedPortfolio:
    reason_codes = ["RISK_EVENT_BELOW_THRESHOLD"]
    if evaluation.unsupported_buckets:
        reason_codes = ["RISK_EVENT_UNSUPPORTED_EXPOSURE_BUCKET"]
    return RiskEventExcludedPortfolio(
        portfolio_id=evaluation.portfolio.portfolio_id,
        impact_score=evaluation.impact_score,
        reason_codes=reason_codes,
    )


def _supportability_state(
    *,
    affected: list[RiskEventAffectedPortfolio],
    excluded: list[RiskEventExcludedPortfolio],
) -> tuple[RiskEventCohortSupportabilityState, list[str]]:
    supportability = RiskEventCohortSupportabilityState.READY
    reason_codes = ["RISK_EVENT_AFFECTED_COHORT_READY"]
    unsupported_bucket_seen = any(
        "RISK_EVENT_UNSUPPORTED_EXPOSURE_BUCKET" in portfolio.reason_codes for portfolio in excluded
    )
    if unsupported_bucket_seen:
        supportability = RiskEventCohortSupportabilityState.DEGRADED
        reason_codes.append("RISK_EVENT_PARTIAL_UNSUPPORTED_EXPOSURE_BUCKETS")
    if not affected:
        supportability = RiskEventCohortSupportabilityState.PENDING_REVIEW
        reason_codes.append("RISK_EVENT_NO_AFFECTED_PORTFOLIOS")
    return supportability, sorted(set(reason_codes))


def _request_fingerprint(request: RiskEventAffectedCohortRequest) -> str:
    payload = request.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _cohort_id(request_fingerprint: str) -> str:
    return "risk_event_cohort_" + request_fingerprint.removeprefix("sha256:")[:16]
