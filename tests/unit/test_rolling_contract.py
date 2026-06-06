import copy

import pytest
from pydantic import ValidationError
from typing import Any, cast

from app.contracts.rolling import (
    RollingAnalyticsRequest,
    RollingInputMode,
    RollingMetricSummary,
    RollingOptions,
    RollingResponse,
)
from app.contracts.rolling_inputs import RollingAnalyticsRequest as RollingAnalyticsRequestSource
from app.contracts.rolling_outputs import RollingResponse as RollingResponseSource
from app.contracts.rolling_metric_outputs import (
    RollingMetricSummary as RollingMetricSummarySource,
)
from app.contracts.rolling_metric_summary_outputs import (
    RollingMetricSummary as RollingMetricSummaryImplementation,
)
from app.contracts.rolling_period_field_examples import (
    ROLLING_PERIOD_BENCHMARK_CONTEXT_EXAMPLE,
    ROLLING_PERIOD_QUALITY_FLAGS_EXAMPLE,
    ROLLING_PERIOD_RISK_FREE_CONTEXT_EXAMPLE,
    ROLLING_PERIOD_WINDOW_RESULTS_EXAMPLE,
)
from app.contracts.rolling_period_outputs import RollingPeriodResult
from app.contracts.rolling_request_inputs import (
    RollingAnalyticsRequest as RollingAnalyticsRequestImplementation,
)
from app.contracts.rolling_response_field_examples import (
    ROLLING_BENCHMARK_CONTEXT_EXAMPLE,
    ROLLING_CALCULATION_SUPPORTABILITY_EXAMPLE,
    ROLLING_REQUESTED_METRICS_EXAMPLE,
    ROLLING_RESPONSE_METADATA_EXAMPLE,
    ROLLING_RESPONSE_RESULTS_EXAMPLE,
    ROLLING_RESPONSE_SCOPE_EXAMPLE,
    ROLLING_RISK_FREE_CONTEXT_EXAMPLE,
)
from app.contracts.rolling_response_outputs import (
    RollingResponse as RollingResponseImplementation,
)
from app.contracts.rolling_response_envelope_outputs import (
    RollingResponse as RollingResponseEnvelope,
)
from app.contracts.rolling_metadata_outputs import RollingMetadata


BASE_STATELESS_PAYLOAD = {
    "input_mode": "stateless",
    "stateless_input": {
        "scope": {"as_of_date": "2026-02-28", "net_or_gross": "NET"},
        "periods": [{"type": "YTD", "name": "YTD"}],
        "returns": [
            {"date": "2026-01-02", "value": 0.45},
            {"date": "2026-01-03", "value": -0.22},
            {"date": "2026-01-06", "value": 0.11},
        ],
        "benchmark_returns": [
            {"date": "2026-01-02", "value": 0.31},
            {"date": "2026-01-03", "value": -0.10},
            {"date": "2026-01-06", "value": 0.08},
        ],
        "risk_free_returns": [
            {"date": "2026-01-02", "value": 0.01},
            {"date": "2026-01-03", "value": 0.01},
            {"date": "2026-01-06", "value": 0.01},
        ],
        "rolling_options": {
            "window_lengths": [2, 3],
            "metrics": [
                "ROLLING_VOLATILITY",
                "ROLLING_SHARPE",
                "ROLLING_BETA",
                "ROLLING_TRACKING_ERROR",
                "ROLLING_INFORMATION_RATIO",
                "ROLLING_MAX_DRAWDOWN",
            ],
        },
    },
}


def test_rolling_contract_module_preserves_public_import_surface() -> None:
    assert RollingAnalyticsRequest is RollingAnalyticsRequestSource
    assert RollingAnalyticsRequest is RollingAnalyticsRequestImplementation
    assert RollingResponse is RollingResponseSource
    assert RollingResponse is RollingResponseImplementation
    assert RollingResponse is RollingResponseEnvelope
    assert RollingMetricSummary is RollingMetricSummarySource
    assert RollingMetricSummary is RollingMetricSummaryImplementation


def test_rolling_response_schema_uses_governed_field_examples() -> None:
    response_properties = RollingResponseEnvelope.model_json_schema()["properties"]
    metadata_properties = RollingMetadata.model_json_schema()["properties"]

    assert response_properties["scope"]["example"] == ROLLING_RESPONSE_SCOPE_EXAMPLE
    assert response_properties["results"]["example"] == ROLLING_RESPONSE_RESULTS_EXAMPLE
    assert response_properties["metadata"]["example"] == ROLLING_RESPONSE_METADATA_EXAMPLE
    assert metadata_properties["requested_metrics"]["example"] == ROLLING_REQUESTED_METRICS_EXAMPLE
    assert metadata_properties["benchmark_context"]["example"] == ROLLING_BENCHMARK_CONTEXT_EXAMPLE
    assert metadata_properties["risk_free_context"]["example"] == ROLLING_RISK_FREE_CONTEXT_EXAMPLE
    assert (
        metadata_properties["calculation_supportability"]["example"]
        == ROLLING_CALCULATION_SUPPORTABILITY_EXAMPLE
    )


def test_rolling_period_schema_uses_governed_field_examples() -> None:
    properties = RollingPeriodResult.model_json_schema()["properties"]

    assert properties["benchmark_context"]["example"] == ROLLING_PERIOD_BENCHMARK_CONTEXT_EXAMPLE
    assert properties["risk_free_context"]["example"] == ROLLING_PERIOD_RISK_FREE_CONTEXT_EXAMPLE
    assert properties["window_results"]["example"] == ROLLING_PERIOD_WINDOW_RESULTS_EXAMPLE
    assert properties["quality_flags"]["example"] == ROLLING_PERIOD_QUALITY_FLAGS_EXAMPLE


def test_rolling_contract_accepts_stateless_payload() -> None:
    request = RollingAnalyticsRequest.model_validate(BASE_STATELESS_PAYLOAD)
    assert request.input_mode == RollingInputMode.STATELESS
    assert request.stateless_input is not None
    assert request.stateless_input.rolling_options.window_lengths == [2, 3]


def test_rolling_contract_requires_stateless_input() -> None:
    with pytest.raises(ValueError, match="stateless_input is required"):
        RollingAnalyticsRequest.model_validate({"input_mode": "stateless"})


def test_rolling_contract_requires_stateful_input() -> None:
    with pytest.raises(ValueError, match="stateful_input is required"):
        RollingAnalyticsRequest.model_validate({"input_mode": "stateful"})


def test_rolling_contract_rejects_simulation_mode_from_public_contract() -> None:
    with pytest.raises(ValidationError):
        RollingAnalyticsRequest.model_validate({"input_mode": "simulation"})


def test_rolling_contract_rejects_duplicate_period_names() -> None:
    payload = copy.deepcopy(BASE_STATELESS_PAYLOAD)
    stateless_input = cast(dict[str, Any], payload["stateless_input"])
    stateless_input["periods"] = [
        {"type": "YTD", "name": "P1"},
        {"type": "MTD", "name": "P1"},
    ]

    with pytest.raises(ValueError, match="Duplicate period names"):
        RollingAnalyticsRequest.model_validate(payload)


def test_rolling_contract_requires_benchmark_for_benchmark_metrics() -> None:
    payload = copy.deepcopy(BASE_STATELESS_PAYLOAD)
    stateless_input = cast(dict[str, Any], payload["stateless_input"])
    stateless_input["benchmark_returns"] = []

    with pytest.raises(ValueError, match="benchmark_returns are required"):
        RollingAnalyticsRequest.model_validate(payload)


def test_rolling_contract_requires_risk_free_for_sharpe() -> None:
    payload = copy.deepcopy(BASE_STATELESS_PAYLOAD)
    stateless_input = cast(dict[str, Any], payload["stateless_input"])
    stateless_input["risk_free_returns"] = []

    with pytest.raises(ValueError, match="risk_free_returns are required"):
        RollingAnalyticsRequest.model_validate(payload)


def test_rolling_contract_rejects_duplicate_window_lengths() -> None:
    payload = copy.deepcopy(BASE_STATELESS_PAYLOAD)
    stateless_input = cast(dict[str, Any], payload["stateless_input"])
    rolling_options = copy.deepcopy(cast(dict[str, Any], stateless_input["rolling_options"]))
    rolling_options["window_lengths"] = [21, 21]
    stateless_input["rolling_options"] = rolling_options

    with pytest.raises(ValueError, match="window_lengths must be unique"):
        RollingAnalyticsRequest.model_validate(payload)


def test_rolling_options_default_metrics_are_populated() -> None:
    options = RollingOptions()
    assert options.metrics == [
        "ROLLING_VOLATILITY",
        "ROLLING_SHARPE",
        "ROLLING_BETA",
        "ROLLING_TRACKING_ERROR",
        "ROLLING_INFORMATION_RATIO",
        "ROLLING_MAX_DRAWDOWN",
    ]


def test_rolling_contract_rejects_empty_and_too_short_window_lengths() -> None:
    for window_lengths, expected_message in [
        ([], "window_lengths must contain at least one window"),
        ([1], "window_lengths must be greater than 1"),
    ]:
        payload = copy.deepcopy(BASE_STATELESS_PAYLOAD)
        stateless_input = cast(dict[str, Any], payload["stateless_input"])
        rolling_options = copy.deepcopy(cast(dict[str, Any], stateless_input["rolling_options"]))
        rolling_options["window_lengths"] = window_lengths
        stateless_input["rolling_options"] = rolling_options

        with pytest.raises(ValueError, match=expected_message):
            RollingAnalyticsRequest.model_validate(payload)


def test_rolling_contract_rejects_duplicate_stateful_period_names() -> None:
    with pytest.raises(ValueError, match="Duplicate period names"):
        RollingAnalyticsRequest.model_validate(
            {
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-02-28",
                    "periods": [
                        {"type": "YTD", "name": "P1"},
                        {"type": "MTD", "name": "P1"},
                    ],
                },
            }
        )
