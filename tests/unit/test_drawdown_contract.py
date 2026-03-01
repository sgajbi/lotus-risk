import pytest

from app.contracts.drawdown import DrawdownAnalyticsRequest, DrawdownInputMode


def _stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": -0.6},
                {"date": "2026-01-03", "value": 0.4},
            ],
        },
    }


def test_drawdown_contract_requires_stateless_input() -> None:
    with pytest.raises(ValueError, match="stateless_input is required"):
        DrawdownAnalyticsRequest.model_validate({"input_mode": "stateless"})


def test_drawdown_contract_requires_stateful_input() -> None:
    with pytest.raises(ValueError, match="stateful_input is required"):
        DrawdownAnalyticsRequest.model_validate({"input_mode": "stateful"})


def test_drawdown_contract_rejects_simulation_mode_in_rfc_slice() -> None:
    payload = {
        "input_mode": "simulation",
        "simulation_input": {
            "portfolio_id": "DEMO_DPM_EUR_001",
            "as_of_date": "2026-02-28",
            "periods": [{"type": "YTD"}],
        },
    }
    request = DrawdownAnalyticsRequest.model_validate(payload)
    assert request.input_mode == DrawdownInputMode.SIMULATION


def test_drawdown_contract_requires_simulation_input() -> None:
    with pytest.raises(ValueError, match="simulation_input is required"):
        DrawdownAnalyticsRequest.model_validate({"input_mode": "simulation"})


def test_drawdown_contract_rejects_duplicate_period_names() -> None:
    payload = _stateless_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["periods"] = [
        {"type": "YTD", "name": "dup"},
        {"type": "MTD", "name": "dup"},
    ]
    with pytest.raises(ValueError, match="Duplicate period names"):
        DrawdownAnalyticsRequest.model_validate(payload)


def test_drawdown_contract_accepts_stateful_payload() -> None:
    request = DrawdownAnalyticsRequest.model_validate(
        {
            "input_mode": "stateful",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-28",
                "client_id": "CLIENT_1000123",
                "periods": [{"type": "YTD", "name": "YTD"}],
            },
            "analysis_options": {"top_n_episodes": 3, "cdar_alpha": 0.95},
        }
    )
    assert request.input_mode == DrawdownInputMode.STATEFUL
    assert request.stateful_input is not None
    assert request.analysis_options.top_n_episodes == 3


def test_drawdown_contract_rejects_invalid_cdar_alpha() -> None:
    payload = _stateless_payload()
    payload["analysis_options"] = {"cdar_alpha": 0.92}
    with pytest.raises(ValueError, match="cdar_alpha must be one of"):
        DrawdownAnalyticsRequest.model_validate(payload)
