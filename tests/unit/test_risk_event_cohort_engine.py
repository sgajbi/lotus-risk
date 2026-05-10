from __future__ import annotations

import pytest

from app.contracts.risk_event_cohort import (
    RiskEventAffectedCohortRequest,
    RiskEventCohortSupportabilityState,
)
from app.services.risk_event_cohort_engine import evaluate_risk_event_affected_cohort


def _request(**overrides: object) -> RiskEventAffectedCohortRequest:
    payload: dict[str, object] = {
        "risk_event_id": "RISK_EVENT_2026_Q2_RATES_UP",
        "as_of_date": "2026-05-10",
        "minimum_impact_score": 0.05,
        "portfolios": [
            {
                "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                "mandate_id": "MANDATE-PB-SG-GLOBAL-BAL-001",
                "portfolio_manager_id": "pm-singapore-01",
                "exposure_weights": {
                    "EQUITY": 0.55,
                    "FIXED_INCOME": 0.35,
                    "CASH": 0.10,
                },
            },
            {
                "portfolio_id": "PB_SG_LOW_RISK_002",
                "mandate_id": "MANDATE-PB-SG-LOW-RISK-002",
                "portfolio_manager_id": "pm-singapore-01",
                "exposure_weights": {
                    "FIXED_INCOME": 0.10,
                    "CASH": 0.90,
                },
            },
        ],
    }
    payload.update(overrides)
    return RiskEventAffectedCohortRequest.model_validate(payload)


def test_risk_event_affected_cohort_returns_source_owned_membership() -> None:
    response = evaluate_risk_event_affected_cohort(_request())

    assert response.risk_event_id == "RISK_EVENT_2026_Q2_RATES_UP"
    assert response.display_name == "Rates-up inflation persistence"
    assert response.metadata.product_name == "RiskEventAffectedCohort"
    assert response.metadata.product_version == "v1"
    assert response.metadata.source_service == "lotus-risk"
    assert response.metadata.calculation_supportability == RiskEventCohortSupportabilityState.READY
    assert response.cohort_id.startswith("risk_event_cohort_")
    assert response.reason_codes == ["RISK_EVENT_AFFECTED_COHORT_READY"]
    assert [member.portfolio_id for member in response.affected_portfolios] == [
        "PB_SG_GLOBAL_BAL_001"
    ]
    member = response.affected_portfolios[0]
    assert member.impact_score == 0.0745
    assert member.dominant_bucket == "FIXED_INCOME"
    assert member.source_ref == (
        "risk-event-cohort:RISK_EVENT_2026_Q2_RATES_UP:2026-05-10:PB_SG_GLOBAL_BAL_001"
    )
    assert member.reason_codes == ["RISK_EVENT_THRESHOLD_BREACHED"]
    assert [excluded.portfolio_id for excluded in response.excluded_portfolios] == [
        "PB_SG_LOW_RISK_002"
    ]


def test_risk_event_affected_cohort_degrades_unsupported_exposure_bucket() -> None:
    response = evaluate_risk_event_affected_cohort(
        _request(
            portfolios=[
                {
                    "portfolio_id": "PB_SG_PRIVATE_MARKETS_003",
                    "exposure_weights": {"PRIVATE_CREDIT": 1.0},
                }
            ]
        )
    )

    assert (
        response.metadata.calculation_supportability
        == RiskEventCohortSupportabilityState.PENDING_REVIEW
    )
    assert response.affected_portfolios == []
    assert response.excluded_portfolios[0].reason_codes == [
        "RISK_EVENT_UNSUPPORTED_EXPOSURE_BUCKET"
    ]
    assert "RISK_EVENT_NO_AFFECTED_PORTFOLIOS" in response.reason_codes
    assert "RISK_EVENT_PARTIAL_UNSUPPORTED_EXPOSURE_BUCKETS" in response.reason_codes


def test_risk_event_affected_cohort_rejects_unknown_event() -> None:
    with pytest.raises(ValueError, match="Unsupported risk_event_id"):
        evaluate_risk_event_affected_cohort(_request(risk_event_id="RISK_EVENT_UNKNOWN"))
