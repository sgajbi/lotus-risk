from __future__ import annotations

import pytest

from app.contracts.scenario import RegimeScenarioPackRequest, ScenarioSupportabilityState
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
    assert response.metadata.request_fingerprint.startswith("sha256:")


def test_regime_scenario_pack_evaluation_flags_threshold_breach() -> None:
    response = evaluate_regime_scenario_pack(_request(maximum_allowed_loss_pct=0.05))

    assert response.breach is True
    assert (
        response.metadata.calculation_supportability == ScenarioSupportabilityState.PENDING_REVIEW
    )
    assert "REGIME_SCENARIO_POLICY_THRESHOLD_BREACH" in response.reason_codes


def test_regime_scenario_pack_evaluation_degrades_for_unsupported_exposure_bucket() -> None:
    response = evaluate_regime_scenario_pack(
        _request(exposures=[{"bucket": "PRIVATE_CREDIT", "weight": 1.0}])
    )

    assert response.metadata.calculation_supportability == ScenarioSupportabilityState.DEGRADED
    assert "REGIME_SCENARIO_UNSUPPORTED_EXPOSURE_BUCKET" in response.reason_codes


def test_regime_scenario_pack_evaluation_rejects_unknown_pack() -> None:
    with pytest.raises(ValueError, match="Unsupported scenario_pack_id"):
        evaluate_regime_scenario_pack(_request(scenario_pack_id="UNKNOWN_PACK"))
