import pytest
from pydantic import ValidationError

from app.contracts.risk import RiskAnalyticsRequest, RiskInputMode, RiskResponse
from app.contracts.risk_inputs import RiskAnalyticsRequest as RiskAnalyticsRequestSource
from app.contracts.risk_request_inputs import RiskAnalyticsRequest as RiskAnalyticsRequestModule
from app.contracts.risk_outputs import RiskResponse as RiskResponseSource
from app.contracts.risk_response_outputs import RiskResponse as RiskResponseModule


def test_risk_contract_module_preserves_public_import_surface() -> None:
    assert RiskAnalyticsRequest is RiskAnalyticsRequestSource
    assert RiskAnalyticsRequest is RiskAnalyticsRequestModule
    assert RiskResponse is RiskResponseSource
    assert RiskResponse is RiskResponseModule


def _stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
            "portfolio_open_date": "2024-01-01",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY"],
            "returns": [
                {"date": "2025-01-02", "value": 0.8},
                {"date": "2025-01-03", "value": -0.2},
            ],
        },
    }


def test_risk_contract_requires_stateless_input_for_stateless_mode() -> None:
    with pytest.raises(ValueError, match="stateless_input is required"):
        RiskAnalyticsRequest.model_validate({"input_mode": "stateless"})


def test_risk_contract_requires_stateful_input_for_stateful_mode() -> None:
    with pytest.raises(ValueError, match="stateful_input is required"):
        RiskAnalyticsRequest.model_validate({"input_mode": "stateful"})


def test_risk_contract_rejects_simulation_mode_from_public_contract() -> None:
    with pytest.raises(ValidationError):
        RiskAnalyticsRequest.model_validate({"input_mode": "simulation"})


def test_risk_contract_rejects_duplicate_period_names() -> None:
    payload = _stateless_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["periods"] = [
        {"type": "YTD", "name": "DUP"},
        {"type": "MTD", "name": "DUP"},
    ]
    with pytest.raises(ValueError, match="Duplicate period names"):
        RiskAnalyticsRequest.model_validate(payload)


def test_risk_contract_rejects_unknown_top_level_fields() -> None:
    payload = _stateless_payload()
    payload["legacy_field"] = "bad"
    with pytest.raises(ValidationError):
        RiskAnalyticsRequest.model_validate(payload)


def test_risk_contract_accepts_mode_specific_payloads() -> None:
    request = RiskAnalyticsRequest.model_validate(_stateless_payload())
    assert request.input_mode == RiskInputMode.STATELESS
    assert request.stateless_input is not None


def test_risk_contract_accepts_stateful_payload_with_metric_spec() -> None:
    payload = {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-02-27",
            "net_or_gross": "NET",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY", "VAR"],
        },
    }
    request = RiskAnalyticsRequest.model_validate(payload)
    assert request.input_mode == RiskInputMode.STATEFUL
    assert request.stateful_input is not None
    assert request.stateful_input.options.frequency == "DAILY"
