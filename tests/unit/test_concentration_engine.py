from app.contracts.concentration import ConcentrationRequest
from app.services.concentration_engine import _compute_hhi, calculate_concentration


def test_compute_hhi_handles_empty_and_zero_total() -> None:
    assert _compute_hhi([]) == 0.0
    assert _compute_hhi([0.0, 0.0]) == 0.0


def test_compute_hhi_equal_weights() -> None:
    assert _compute_hhi([10.0, 10.0]) == 5000.0


def test_calculate_concentration_uses_projected_values_when_provided() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "current_positions": [
                {"security_id": "A", "quantity": 10},
                {"security_id": "B", "quantity": 10},
            ],
            "projected_positions": [
                {"security_id": "A", "proposed_quantity": 15},
                {"security_id": "B", "proposed_quantity": 5},
            ],
        }
    )
    response = calculate_concentration(request).model_dump()
    assert response["source_service"] == "lotus-risk"
    assert response["risk_proxy"]["hhi_current"] == 5000.0
    assert response["risk_proxy"]["hhi_proposed"] == 6250.0
    assert response["risk_proxy"]["hhi_delta"] == 1250.0


def test_calculate_concentration_falls_back_to_current_when_no_projected() -> None:
    request = ConcentrationRequest.model_validate(
        {"current_positions": [{"security_id": "A", "quantity": 10}]}
    )
    response = calculate_concentration(request).model_dump()
    assert response["risk_proxy"]["hhi_current"] == 10000.0
    assert response["risk_proxy"]["hhi_proposed"] == 10000.0
    assert response["risk_proxy"]["hhi_delta"] == 0.0
