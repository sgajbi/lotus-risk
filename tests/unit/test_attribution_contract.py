from copy import deepcopy
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.contracts.attribution import AttributionInputMode, HistoricalAttributionRequest


BASE_STATELESS_PAYLOAD: dict[str, Any] = {
    "input_mode": "stateless",
    "stateless_input": {
        "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
        "periods": [{"type": "YTD", "name": "YTD"}],
        "returns": [
            {"date": "2026-01-02", "value": 0.6},
            {"date": "2026-01-03", "value": -0.4},
        ],
        "benchmark_returns": [
            {"date": "2026-01-02", "value": 0.5},
            {"date": "2026-01-03", "value": -0.3},
        ],
        "exposure_history": [
            {
                "date": "2026-01-02",
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "weight": 0.55,
            },
            {
                "date": "2026-01-03",
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "weight": 0.50,
            },
        ],
        "benchmark_exposure_history": [
            {
                "date": "2026-01-02",
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "weight": 0.45,
            },
            {
                "date": "2026-01-03",
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "weight": 0.44,
            },
        ],
        "attribution_options": {
            "attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
            "metrics": ["VOLATILITY", "TRACKING_ERROR"],
            "grouping_dimensions": ["SECTOR"],
        },
    },
}


def test_attribution_contract_accepts_stateless_payload() -> None:
    request = HistoricalAttributionRequest.model_validate(BASE_STATELESS_PAYLOAD)
    assert request.input_mode == AttributionInputMode.STATELESS
    assert request.stateless_input is not None


def test_attribution_contract_requires_stateless_input() -> None:
    with pytest.raises(ValueError, match="stateless_input is required"):
        HistoricalAttributionRequest.model_validate({"input_mode": "stateless"})


def test_attribution_contract_requires_stateful_input() -> None:
    with pytest.raises(ValueError, match="stateful_input is required"):
        HistoricalAttributionRequest.model_validate({"input_mode": "stateful"})


def test_attribution_contract_rejects_simulation_mode_from_public_contract() -> None:
    with pytest.raises(ValidationError):
        HistoricalAttributionRequest.model_validate({"input_mode": "simulation"})


def test_attribution_contract_requires_benchmark_data_for_active_risk() -> None:
    payload = deepcopy(BASE_STATELESS_PAYLOAD)
    stateless_input = cast(dict[str, Any], payload["stateless_input"])
    stateless_input["benchmark_returns"] = []
    with pytest.raises(ValueError, match="benchmark_returns are required"):
        HistoricalAttributionRequest.model_validate(payload)


def test_attribution_contract_requires_benchmark_exposures_for_active_risk() -> None:
    payload = deepcopy(BASE_STATELESS_PAYLOAD)
    stateless_input = cast(dict[str, Any], payload["stateless_input"])
    stateless_input["benchmark_exposure_history"] = []
    with pytest.raises(ValueError, match="benchmark_exposure_history are required"):
        HistoricalAttributionRequest.model_validate(payload)


def test_attribution_options_reject_empty_lists() -> None:
    for field_name, expected_message in [
        ("attribution_types", "attribution_types must include at least one value"),
        ("metrics", "metrics must include at least one value"),
        ("grouping_dimensions", "grouping_dimensions must include at least one value"),
    ]:
        payload = deepcopy(BASE_STATELESS_PAYLOAD)
        stateless_input = cast(dict[str, Any], payload["stateless_input"])
        options = cast(dict[str, Any], stateless_input["attribution_options"])
        options[field_name] = []

        with pytest.raises(ValueError, match=expected_message):
            HistoricalAttributionRequest.model_validate(payload)


def test_attribution_contract_rejects_duplicate_period_names() -> None:
    payload = deepcopy(BASE_STATELESS_PAYLOAD)
    stateless_input = cast(dict[str, Any], payload["stateless_input"])
    stateless_input["periods"] = [
        {"type": "YTD", "name": "P1"},
        {"type": "MTD", "name": "P1"},
    ]

    with pytest.raises(ValueError, match="Duplicate period names"):
        HistoricalAttributionRequest.model_validate(payload)


def test_stateful_attribution_contract_accepts_active_risk_issuer_grouping() -> None:
    request = HistoricalAttributionRequest.model_validate(
        {
            "input_mode": "stateful",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-04",
                "periods": [{"type": "YTD", "name": "YTD"}],
                "attribution_options": {
                    "attribution_types": ["ACTIVE_RISK"],
                    "metrics": ["TRACKING_ERROR"],
                    "grouping_dimensions": ["ISSUER"],
                },
            },
        }
    )

    assert request.stateful_input is not None
    assert request.stateful_input.attribution_options.grouping_dimensions == ["ISSUER"]


def test_stateful_attribution_contract_rejects_custom_grouping() -> None:
    with pytest.raises(ValueError, match="grouping_dimension=CUSTOM"):
        HistoricalAttributionRequest.model_validate(
            {
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-04",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "attribution_options": {
                        "attribution_types": ["TOTAL_RISK"],
                        "metrics": ["VOLATILITY"],
                        "grouping_dimensions": ["CUSTOM"],
                    },
                },
            }
        )
