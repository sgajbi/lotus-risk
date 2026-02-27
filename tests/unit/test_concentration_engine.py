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
            "currentPositions": [
                {"securityId": "A", "quantity": 10},
                {"securityId": "B", "quantity": 10},
            ],
            "projectedPositions": [
                {"securityId": "A", "proposedQuantity": 15},
                {"securityId": "B", "proposedQuantity": 5},
            ],
        }
    )
    response = calculate_concentration(request).model_dump(by_alias=True)
    assert response["sourceService"] == "lotus-risk"
    assert response["riskProxy"]["hhiCurrent"] == 5000.0
    assert response["riskProxy"]["hhiProposed"] == 6250.0
    assert response["riskProxy"]["hhiDelta"] == 1250.0


def test_calculate_concentration_falls_back_to_current_when_no_projected() -> None:
    request = ConcentrationRequest.model_validate(
        {"currentPositions": [{"securityId": "A", "quantity": 10}]}
    )
    response = calculate_concentration(request).model_dump(by_alias=True)
    assert response["riskProxy"]["hhiCurrent"] == 10000.0
    assert response["riskProxy"]["hhiProposed"] == 10000.0
    assert response["riskProxy"]["hhiDelta"] == 0.0
