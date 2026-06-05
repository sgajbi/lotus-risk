import pytest
from pydantic import ValidationError

from app.contracts.concentration import (
    ConcentrationRequest,
    ConcentrationResponse,
    IssuerConcentration,
)
from app.contracts.concentration_inputs import ConcentrationRequest as ConcentrationRequestSource
from app.contracts.concentration_outputs import ConcentrationResponse as ConcentrationResponseSource
from app.contracts.concentration_request_inputs import (
    ConcentrationRequest as ConcentrationRequestImplementation,
)
from app.contracts.concentration_metric_field_examples import (
    TOP_ISSUER_CURRENT_EXAMPLE,
    TOP_ISSUER_PROPOSED_EXAMPLE,
    TOP_POSITION_CURRENT_EXAMPLE,
    TOP_POSITION_PROPOSED_EXAMPLE,
)
from app.contracts.concentration_response_field_examples import (
    CONCENTRATION_ISSUER_EXAMPLE,
    CONCENTRATION_METADATA_EXAMPLE,
    CONCENTRATION_RISK_PROXY_EXAMPLE,
    CONCENTRATION_SINGLE_POSITION_EXAMPLE,
    CONCENTRATION_VALUATION_CONTEXT_EXAMPLE,
)
from app.contracts.concentration_metric_outputs import (
    SinglePositionConcentration,
    IssuerConcentration as IssuerConcentrationSource,
)
from app.contracts.concentration_issuer_metric_outputs import (
    IssuerConcentration as IssuerConcentrationImplementation,
)
from app.contracts.concentration_response_outputs import (
    ConcentrationResponse as ConcentrationResponseImplementation,
)
from app.contracts.concentration_response_envelope_outputs import (
    ConcentrationResponse as ConcentrationResponseEnvelope,
)


def test_concentration_contract_module_preserves_public_import_surface() -> None:
    assert ConcentrationRequest is ConcentrationRequestSource
    assert ConcentrationRequest is ConcentrationRequestImplementation
    assert ConcentrationResponse is ConcentrationResponseSource
    assert ConcentrationResponse is ConcentrationResponseImplementation
    assert ConcentrationResponse is ConcentrationResponseEnvelope
    assert IssuerConcentration is IssuerConcentrationSource
    assert IssuerConcentration is IssuerConcentrationImplementation


def test_concentration_response_schema_uses_governed_field_examples() -> None:
    properties = ConcentrationResponseEnvelope.model_json_schema()["properties"]

    assert properties["risk_proxy"]["example"] == CONCENTRATION_RISK_PROXY_EXAMPLE
    assert (
        properties["single_position_concentration"]["example"]
        == CONCENTRATION_SINGLE_POSITION_EXAMPLE
    )
    assert properties["issuer_concentration"]["example"] == CONCENTRATION_ISSUER_EXAMPLE
    assert properties["valuation_context"]["example"] == CONCENTRATION_VALUATION_CONTEXT_EXAMPLE
    assert properties["metadata"]["example"] == CONCENTRATION_METADATA_EXAMPLE


def test_concentration_metric_schema_uses_governed_driver_examples() -> None:
    issuer_properties = IssuerConcentrationSource.model_json_schema()["properties"]
    position_properties = SinglePositionConcentration.model_json_schema()["properties"]

    assert issuer_properties["top_issuer_current"]["example"] == TOP_ISSUER_CURRENT_EXAMPLE
    assert issuer_properties["top_issuer_proposed"]["example"] == TOP_ISSUER_PROPOSED_EXAMPLE
    assert position_properties["top_position_current"]["example"] == TOP_POSITION_CURRENT_EXAMPLE
    assert position_properties["top_position_proposed"]["example"] == TOP_POSITION_PROPOSED_EXAMPLE


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
