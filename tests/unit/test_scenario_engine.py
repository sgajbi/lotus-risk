from __future__ import annotations

from dataclasses import replace

import pytest

from app.contracts.scenario import (
    RegimeScenarioPackRequest,
    RegimeScenarioPackResponse,
    ScenarioPackApprovalStatus,
    ScenarioSupportabilityState,
)
from app.contracts.scenario_inputs import (
    RegimeScenarioPackRequest as RegimeScenarioPackRequestSource,
)
from app.contracts.scenario_outputs import (
    RegimeScenarioPackResponse as RegimeScenarioPackResponseSource,
)
from app.services import scenario_engine
from app.services.scenario_engine import evaluate_regime_scenario_pack


def _request(**overrides: object) -> RegimeScenarioPackRequest:
    payload: dict[str, object] = {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "as_of_date": "2026-05-03",
        "maximum_allowed_loss_pct": 0.12,
        "exposures": [
            {"bucket": "EQUITY", "weight": 0.55},
            {"bucket": "FIXED_INCOME", "weight": 0.35},
            {"bucket": "CASH", "weight": 0.10},
        ],
    }
    payload.update(overrides)
    return RegimeScenarioPackRequest.model_validate(payload)


def test_scenario_contract_module_preserves_public_import_surface() -> None:
    assert RegimeScenarioPackRequest is RegimeScenarioPackRequestSource
    assert RegimeScenarioPackResponse is RegimeScenarioPackResponseSource


def test_regime_scenario_pack_evaluation_returns_source_owned_worst_case_loss() -> None:
    response = evaluate_regime_scenario_pack(_request())

    assert response.scenario_pack_id == "CIO_REGIME_2026_Q2"
    assert response.metadata.product_name == "RegimeScenarioPackEvaluation"
    assert response.metadata.product_version == "v1"
    assert response.metadata.source_service == "lotus-risk"
    assert response.metadata.calculation_supportability == ScenarioSupportabilityState.READY
    assert response.worst_case_loss_pct == 0.106
    assert response.breach is False
    assert response.reason_codes == ["REGIME_SCENARIO_PACK_READY"]
    assert response.governance_evidence.cio_approval_status == "approved"
    assert response.governance_evidence.effective_period_status == "active"
    assert response.governance_evidence.applicability_status == "applicable"
    assert response.governance_evidence.portfolio_applicability_ref == (
        "CIO-REGIME-2026-Q2-APPROVAL-APP-PB_SG_GLOBAL_BAL_001"
    )
    assert response.metadata.request_fingerprint.startswith("sha256:")
    assert all(not scenario.position_contributions for scenario in response.scenario_results)


def test_regime_scenario_pack_evaluation_returns_security_contribution_rows() -> None:
    response = evaluate_regime_scenario_pack(
        _request(
            exposure_components=[
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "display_name": "Apple Inc.",
                    "bucket": "EQUITY",
                    "weight": 0.30,
                },
                {
                    "security_id": "FO_EQ_MSFT_US",
                    "display_name": "Microsoft Corporation",
                    "bucket": "EQUITY",
                    "weight": 0.25,
                },
                {
                    "security_id": "FO_BOND_UST_2030",
                    "display_name": "United States Treasury 3.875% 2030",
                    "bucket": "FIXED_INCOME",
                    "weight": 0.35,
                },
                {
                    "security_id": "CASH_USD_BOOK_OPERATING",
                    "display_name": "USD Operating Cash",
                    "bucket": "CASH",
                    "weight": 0.10,
                },
            ]
        )
    )

    growth_slowdown = next(
        scenario
        for scenario in response.scenario_results
        if scenario.scenario_id == "growth_slowdown"
    )

    assert response.worst_case_loss_pct == 0.106
    assert [row.security_id for row in growth_slowdown.position_contributions] == [
        "FO_EQ_AAPL_US",
        "FO_EQ_MSFT_US",
        "FO_BOND_UST_2030",
        "CASH_USD_BOOK_OPERATING",
    ]
    assert [row.contribution_loss_pct for row in growth_slowdown.position_contributions] == [
        0.036,
        0.03,
        0.0105,
        0.0,
    ]


def test_regime_scenario_pack_evaluation_rejects_unreconciled_security_components() -> None:
    with pytest.raises(ValueError, match="exposure_components must reconcile"):
        _request(
            exposure_components=[
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "bucket": "EQUITY",
                    "weight": 0.10,
                }
            ]
        )


def test_regime_scenario_pack_evaluation_flags_threshold_breach() -> None:
    response = evaluate_regime_scenario_pack(_request(maximum_allowed_loss_pct=0.05))

    assert response.breach is True
    assert (
        response.metadata.calculation_supportability == ScenarioSupportabilityState.PENDING_REVIEW
    )
    assert "REGIME_SCENARIO_POLICY_THRESHOLD_BREACH" in response.reason_codes


def test_regime_scenario_pack_evaluation_degrades_for_effective_period_exception() -> None:
    response = evaluate_regime_scenario_pack(_request(as_of_date="2026-07-01"))

    assert response.metadata.calculation_supportability == ScenarioSupportabilityState.DEGRADED
    assert response.governance_evidence.effective_period_status == "expired"
    assert "REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION" in response.reason_codes


def test_regime_scenario_pack_evaluation_degrades_before_effective_period() -> None:
    response = evaluate_regime_scenario_pack(_request(as_of_date="2026-03-31"))

    assert response.metadata.calculation_supportability == ScenarioSupportabilityState.DEGRADED
    assert response.governance_evidence.effective_period_status == "not_yet_effective"
    assert "REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION" in response.reason_codes


def test_regime_scenario_pack_evaluation_blocks_when_cio_approval_not_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = scenario_engine.SCENARIO_PACK_GOVERNANCE["CIO_REGIME_2026_Q2"]
    monkeypatch.setitem(
        scenario_engine.SCENARIO_PACK_GOVERNANCE,
        "CIO_REGIME_2026_Q2",
        replace(original, cio_approval_status=ScenarioPackApprovalStatus.NOT_APPROVED),
    )

    response = evaluate_regime_scenario_pack(_request())

    assert response.metadata.calculation_supportability == ScenarioSupportabilityState.BLOCKED
    assert response.governance_evidence.cio_approval_status == "not_approved"
    assert "REGIME_SCENARIO_CIO_APPROVAL_NOT_CONFIRMED" in response.reason_codes


def test_regime_scenario_pack_evaluation_pending_review_without_portfolio_scope() -> None:
    response = evaluate_regime_scenario_pack(_request(portfolio_id=None))

    assert (
        response.metadata.calculation_supportability == ScenarioSupportabilityState.PENDING_REVIEW
    )
    assert response.governance_evidence.applicability_status == "pending_review"
    assert response.governance_evidence.portfolio_applicability_ref is None
    assert "REGIME_SCENARIO_PORTFOLIO_APPLICABILITY_NOT_CONFIRMED" in response.reason_codes


def test_regime_scenario_pack_evaluation_blocks_non_applicable_portfolio() -> None:
    response = evaluate_regime_scenario_pack(_request(portfolio_id="PB_OTHER"))

    assert response.metadata.calculation_supportability == ScenarioSupportabilityState.BLOCKED
    assert response.governance_evidence.applicability_status == "not_applicable"
    assert response.governance_evidence.portfolio_applicability_ref is None
    assert "REGIME_SCENARIO_PORTFOLIO_NOT_APPLICABLE" in response.reason_codes


def test_regime_scenario_pack_evaluation_degrades_for_unsupported_exposure_bucket() -> None:
    response = evaluate_regime_scenario_pack(
        _request(exposures=[{"bucket": "PRIVATE_CREDIT", "weight": 1.0}])
    )

    assert response.metadata.calculation_supportability == ScenarioSupportabilityState.DEGRADED
    assert "REGIME_SCENARIO_UNSUPPORTED_EXPOSURE_BUCKET" in response.reason_codes


def test_regime_scenario_pack_evaluation_rejects_unknown_pack() -> None:
    with pytest.raises(ValueError, match="Unsupported scenario_pack_id"):
        evaluate_regime_scenario_pack(_request(scenario_pack_id="UNKNOWN_PACK"))
