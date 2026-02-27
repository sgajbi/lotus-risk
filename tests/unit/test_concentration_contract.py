import pytest
from pydantic import ValidationError

from app.contracts.concentration import ConcentrationRequest


def test_simulation_input_rejects_ttl_when_reusing_session() -> None:
    with pytest.raises(ValueError, match="session_ttl_hours is not allowed"):
        ConcentrationRequest.model_validate(
            {
                "input_mode": "simulation",
                "simulation_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-02-27",
                    "session_id": "SIM_0001",
                    "session_ttl_hours": 24,
                    "simulation_changes": [],
                },
            }
        )


def test_legacy_payload_rejected() -> None:
    with pytest.raises(ValidationError):
        ConcentrationRequest.model_validate(
            {
                "current_positions": [{"security_id": "A", "quantity": 10}],
                "projected_positions": [{"security_id": "A", "proposed_quantity": 12}],
            }
        )


def test_stateful_mode_requires_stateful_input() -> None:
    with pytest.raises(ValueError, match="stateful_input is required"):
        ConcentrationRequest.model_validate({"input_mode": "stateful"})


def test_simulation_mode_requires_simulation_input() -> None:
    with pytest.raises(ValueError, match="simulation_input is required"):
        ConcentrationRequest.model_validate({"input_mode": "simulation"})


def test_stateless_mode_defaults_to_empty_stateless_input() -> None:
    request = ConcentrationRequest.model_validate({"input_mode": "stateless"})
    assert request.stateless_input is not None
    assert request.stateless_input.current_positions == []
