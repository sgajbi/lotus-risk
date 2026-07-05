from datetime import date, timedelta
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.contracts.rolling import (
    ROLLING_MAX_PERIODS,
    ROLLING_MAX_STATELESS_OBSERVATIONS,
    ROLLING_MAX_TIME_SERIES_POINTS,
    ROLLING_MAX_WINDOW_COUNT,
)
from app.main import app
from app.observability_contracts import RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_core_fakes import RecordingLotusCoreReferenceClient
from tests.support.lotus_performance_fakes import (
    RecordingLotusPerformanceClient,
    build_autowired_lotus_performance_client_class,
)
from tests.support.risk_free_series_payloads import build_risk_free_series_response
from tests.support.returns_series_payloads import (
    JAN_2026_PORTFOLIO_RETURNS,
    JAN_2026_ROLLING_BENCHMARK_RETURNS,
    build_returns_series_response,
)

_AutoWiredLotusPerformanceClient = build_autowired_lotus_performance_client_class(
    response_factory=lambda: build_returns_series_response(
        portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
        benchmark_returns=JAN_2026_ROLLING_BENCHMARK_RETURNS,
    )
)
_EXPECTED_SUPPORTABILITY_METRIC_LABELS = list(RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS)


def _business_dates(count: int) -> list[date]:
    start = date(2020, 1, 1)
    values: list[date] = []
    offset = 0
    while len(values) < count:
        candidate = start + timedelta(days=offset)
        if candidate.weekday() < 5:
            values.append(candidate)
        offset += 1
    return values


def _return_points(count: int) -> list[dict[str, object]]:
    return [{"date": value.isoformat(), "value": 0.01} for value in _business_dates(count)]


def _return_rows(count: int) -> list[tuple[str, str]]:
    return [(value.isoformat(), "0.0100") for value in _business_dates(count)]


def _explicit_periods(count: int) -> list[dict[str, object]]:
    return [
        {
            "type": "EXPLICIT",
            "name": f"P{offset}",
            "from_date": "2020-01-01",
            "to_date": "2030-12-31",
        }
        for offset in range(count)
    ]


def _stateless_payload() -> dict[str, object]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -2.0},
                {"date": "2026-01-04", "value": 0.5},
                {"date": "2026-01-05", "value": 1.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-03", "value": -1.5},
                {"date": "2026-01-04", "value": 0.4},
                {"date": "2026-01-05", "value": 1.0},
            ],
            "risk_free_returns": [
                {"date": "2026-01-02", "value": 0.01},
                {"date": "2026-01-03", "value": 0.01},
                {"date": "2026-01-04", "value": 0.01},
                {"date": "2026-01-05", "value": 0.01},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_SHARPE",
                    "ROLLING_BETA",
                    "ROLLING_TRACKING_ERROR",
                    "ROLLING_INFORMATION_RATIO",
                    "ROLLING_MAX_DRAWDOWN",
                ],
                "include_time_series": True,
            },
        },
    }


def _volatility_only_payload() -> dict[str, object]:
    payload = _stateless_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["benchmark_returns"] = []
    stateless["risk_free_returns"] = []
    stateless["rolling_options"] = {
        "window_lengths": [2],
        "metrics": ["ROLLING_VOLATILITY"],
        "include_time_series": False,
    }
    return payload


def test_rolling_metrics_endpoint_stateless_contract() -> None:
    client = TestClient(app)
    response = client.post("/analytics/risk/rolling-metrics", json=_stateless_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source_service"] == "lotus-risk"
    assert body["input_mode"] == "stateless"
    assert body["metadata"]["methodology_version"] == "rolling_metrics.v1"
    assert body["metadata"]["requested_metrics"] == [
        "ROLLING_VOLATILITY",
        "ROLLING_SHARPE",
        "ROLLING_BETA",
        "ROLLING_TRACKING_ERROR",
        "ROLLING_INFORMATION_RATIO",
        "ROLLING_MAX_DRAWDOWN",
    ]
    assert body["metadata"]["window_lengths_requested"] == [3]
    assert body["metadata"]["window_count_requested"] == 1
    assert body["metadata"]["min_observations_policy"] == "STRICT"
    assert body["metadata"]["include_time_series"] is True
    assert body["metadata"]["benchmark_context"] == {
        "requested": True,
        "requested_metrics": [
            "ROLLING_BETA",
            "ROLLING_TRACKING_ERROR",
            "ROLLING_INFORMATION_RATIO",
        ],
    }
    assert body["metadata"]["risk_free_context"] == {
        "requested": True,
        "requested_metrics": ["ROLLING_SHARPE"],
    }
    assert body["metadata"]["calculation_supportability"] == {
        "state": "stale",
        "reason": "stale_source_observations",
        "freshness_bucket": "stale",
        "metric_labels": _EXPECTED_SUPPORTABILITY_METRIC_LABELS,
        "degraded_metric_count": 0,
        "empty_period_count": 0,
        "evaluated_period_count": 1,
    }
    assert "YTD" in body["results"]
    assert body["results"]["YTD"]["benchmark_series_count"] == 4
    assert body["results"]["YTD"]["aligned_benchmark_series_count"] == 4
    assert body["results"]["YTD"]["risk_free_series_count"] == 4
    assert body["results"]["YTD"]["aligned_risk_free_series_count"] == 4
    assert body["results"]["YTD"]["window_lengths_requested"] == [3]
    assert body["results"]["YTD"]["window_count_requested"] == 1
    assert body["results"]["YTD"]["window_lengths_emitted"] == [3]
    assert body["results"]["YTD"]["window_count_emitted"] == 1
    assert body["results"]["YTD"]["benchmark_context"] == {
        "requested": True,
        "available": True,
        "aligned": True,
        "reason": "APPLIED",
    }
    assert body["results"]["YTD"]["risk_free_context"] == {
        "requested": True,
        "available": True,
        "aligned": True,
        "reason": "APPLIED",
    }
    window = body["results"]["YTD"]["window_results"][0]
    assert window["window_length"] == 3
    assert window["metric_series_context"] == {
        "requested": True,
        "included": True,
        "emitted_point_count": 4,
        "reason": "INCLUDED",
    }
    assert "ROLLING_VOLATILITY" in window["metric_summaries"]
    summary = window["metric_summaries"]["ROLLING_VOLATILITY"]
    assert summary["total_point_count"] == 4
    assert summary["computed_point_count"] >= 1
    assert summary["coverage_ratio"] == pytest.approx(
        summary["computed_point_count"] / summary["total_point_count"]
    )
    assert summary["min_observations_required"] == 3
    assert summary["warmup_point_count"] == 2
    assert summary["non_computed_point_count"] == 2
    assert summary["post_warmup_gap_point_count"] == 0
    assert summary["latest_observation_date"] == "2026-01-05"


def test_rolling_metrics_endpoint_supportability_marks_insufficient_period() -> None:
    client = TestClient(app)
    payload = _stateless_payload()
    payload["stateless_input"]["periods"] = [  # type: ignore[index]
        {
            "type": "EXPLICIT",
            "name": "SHORT",
            "from_date": "2026-01-02",
            "to_date": "2026-01-02",
        }
    ]
    response = client.post("/analytics/risk/rolling-metrics", json=payload)
    assert response.status_code == 200
    assert response.json()["metadata"]["calculation_supportability"] == {
        "state": "degraded",
        "reason": "insufficient_observations",
        "freshness_bucket": "stale",
        "metric_labels": _EXPECTED_SUPPORTABILITY_METRIC_LABELS,
        "degraded_metric_count": 1,
        "empty_period_count": 0,
        "evaluated_period_count": 1,
    }


def test_rolling_metrics_endpoint_stateful_uses_lotus_performance() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
            benchmark_returns=JAN_2026_ROLLING_BENCHMARK_RETURNS,
        )
    )
    core_client = RecordingLotusCoreReferenceClient(
        risk_free_response=build_risk_free_series_response(
            points=[
                {
                    "series_date": "2026-01-02",
                    "value": "0.0365",
                    "value_convention": "annualized_rate",
                },
                {
                    "series_date": "2026-01-05",
                    "value": "0.0365",
                    "value_convention": "annualized_rate",
                },
                {
                    "series_date": "2026-01-06",
                    "value": "0.0365",
                    "value_convention": "annualized_rate",
                },
            ]
        )
    )
    with override_app_runtime(
        lotus_performance_client=recorder,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            headers={"X-Correlation-Id": "corr-rolling-stateful"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": [
                            "ROLLING_VOLATILITY",
                            "ROLLING_SHARPE",
                            "ROLLING_BETA",
                        ],
                    },
                },
            },
        )
    assert response.status_code == 200
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["correlation_id"] == "corr-rolling-stateful"
    payload = recorder.calls[0]["request_payload"]
    assert isinstance(payload, dict)
    assert payload["input_mode"] == "stateful"
    assert payload["stateful_input"] == {}
    assert payload["reporting_currency"] == "USD"
    assert payload["series_selection"]["include_benchmark"] is True
    assert payload["series_selection"]["include_risk_free"] is False
    assert core_client.risk_free_calls
    body = response.json()
    assert body["input_mode"] == "stateful"
    assert body["metadata"]["requested_metrics"] == [
        "ROLLING_VOLATILITY",
        "ROLLING_SHARPE",
        "ROLLING_BETA",
    ]
    assert body["metadata"]["window_lengths_requested"] == [2]
    assert body["metadata"]["window_count_requested"] == 1
    assert body["metadata"]["min_observations_policy"] == "STRICT"
    assert body["metadata"]["include_time_series"] is False
    assert body["metadata"]["benchmark_context"] == {
        "requested": True,
        "requested_metrics": ["ROLLING_BETA"],
    }
    assert body["metadata"]["risk_free_context"] == {
        "requested": True,
        "requested_metrics": ["ROLLING_SHARPE"],
    }
    assert body["results"]["YTD"]["benchmark_series_count"] == 3
    assert body["results"]["YTD"]["aligned_benchmark_series_count"] == 3
    assert body["results"]["YTD"]["risk_free_series_count"] == 3
    assert body["results"]["YTD"]["aligned_risk_free_series_count"] == 3
    assert body["results"]["YTD"]["window_lengths_requested"] == [2]
    assert body["results"]["YTD"]["window_count_requested"] == 1
    assert body["results"]["YTD"]["window_lengths_emitted"] == [2]
    assert body["results"]["YTD"]["window_count_emitted"] == 1
    assert body["results"]["YTD"]["benchmark_context"]["reason"] == "APPLIED"
    assert body["results"]["YTD"]["risk_free_context"]["reason"] == "APPLIED"
    assert body["results"]["YTD"]["window_results"][0]["metric_series"] is None
    assert body["results"]["YTD"]["window_results"][0]["metric_series_context"] == {
        "requested": False,
        "included": False,
        "emitted_point_count": 0,
        "reason": "OMITTED_BY_REQUEST",
    }


def test_rolling_metrics_endpoint_stateful_surfaces_missing_risk_free_after_currency_resolution() -> (
    None
):
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
            benchmark_returns=JAN_2026_ROLLING_BENCHMARK_RETURNS,
        )
    )
    core_client = RecordingLotusCoreReferenceClient()
    with override_app_runtime(
        lotus_performance_client=recorder,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            headers={"X-Correlation-Id": "corr-rolling-missing-rf"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": ["ROLLING_SHARPE"],
                    },
                },
            },
        )

    assert response.status_code == 424
    body = response.json()["error"]
    assert body["code"] == "FAILED_DEPENDENCY"
    assert body["message"] == "Required upstream dependency data is unavailable."
    assert body["correlation_id"] == "corr-rolling-missing-rf"
    assert body["details"]["service"] == "lotus-core"
    assert body["details"]["risk_free_currency"] == "USD"
    assert body["details"]["risk_free_total_points"] == 0
    assert body["details"]["risk_free_missing_dates_count"] == 4
    assert len(recorder.calls) == 1
    payload = recorder.calls[0]["request_payload"]
    assert isinstance(payload, dict)
    assert payload["reporting_currency"] == "USD"
    assert payload["series_selection"] == {
        "include_portfolio": True,
        "include_benchmark": False,
        "include_risk_free": False,
    }
    assert core_client.risk_free_calls
    assert core_client.risk_free_coverage_calls


def test_rolling_metrics_endpoint_stateful_uses_explicit_reporting_currency_for_risk_free() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
        )
    )
    core_client = RecordingLotusCoreReferenceClient(
        risk_free_response=build_risk_free_series_response(
            points=[
                {
                    "series_date": "2026-01-02",
                    "value": "0.0252",
                    "value_convention": "annualized_rate",
                },
                {
                    "series_date": "2026-01-05",
                    "value": "0.0252",
                    "value_convention": "annualized_rate",
                },
                {
                    "series_date": "2026-01-06",
                    "value": "0.0252",
                    "value_convention": "annualized_rate",
                },
            ]
        )
    )

    with override_app_runtime(
        lotus_performance_client=recorder,
        lotus_core_client=core_client,
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            headers={"X-Correlation-Id": "corr-rolling-explicit-rf"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "reporting_currency": "CHF",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": ["ROLLING_SHARPE"],
                    },
                },
            },
        )

    assert response.status_code == 200
    assert core_client.snapshot_calls == []
    risk_free_payload = cast(dict[str, Any], core_client.risk_free_calls[0]["request_payload"])
    assert risk_free_payload["currency"] == "CHF"
    assert risk_free_payload["window"] == {
        "start_date": "2026-01-01",
        "end_date": "2026-01-06",
    }
    performance_payload = cast(dict[str, Any], recorder.calls[0]["request_payload"])
    assert performance_payload["reporting_currency"] == "CHF"
    assert performance_payload["series_selection"]["include_risk_free"] is False


def test_rolling_metrics_endpoint_stateful_rejects_missing_benchmark_returns_for_beta() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=JAN_2026_PORTFOLIO_RETURNS,
        )
    )
    with override_app_runtime(lotus_performance_client=recorder):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            headers={"X-Correlation-Id": "corr-rolling-missing-bmk"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": ["ROLLING_BETA"],
                    },
                },
            },
        )

    assert response.status_code == 424
    body = response.json()["error"]
    assert body["code"] == "FAILED_DEPENDENCY"
    assert body["message"] == "Required upstream dependency data is unavailable."
    assert body["correlation_id"] == "corr-rolling-missing-bmk"
    assert body["details"]["service"] == "lotus-performance"
    request_payload = cast(dict[str, Any], recorder.calls[0]["request_payload"])
    assert request_payload["series_selection"]["include_benchmark"] is True


def test_rolling_metrics_endpoint_stateless_rejects_missing_benchmark_series() -> None:
    client = TestClient(app)
    payload = _stateless_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["benchmark_returns"] = []
    stateless["rolling_options"] = {
        "window_lengths": [3],
        "metrics": ["ROLLING_BETA"],
        "include_time_series": False,
    }
    response = client.post("/analytics/risk/rolling-metrics", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_rolling_metrics_endpoint_stateless_rejects_missing_risk_free_series() -> None:
    client = TestClient(app)
    payload = _stateless_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["risk_free_returns"] = []
    stateless["rolling_options"] = {
        "window_lengths": [3],
        "metrics": ["ROLLING_SHARPE"],
        "include_time_series": False,
    }
    response = client.post("/analytics/risk/rolling-metrics", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_rolling_metrics_endpoint_rejects_too_many_periods() -> None:
    client = TestClient(app)
    payload = _volatility_only_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["periods"] = _explicit_periods(ROLLING_MAX_PERIODS + 1)

    response = client.post("/analytics/risk/rolling-metrics", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_rolling_metrics_endpoint_rejects_too_many_windows() -> None:
    client = TestClient(app)
    payload = _volatility_only_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    rolling_options = cast(dict[str, Any], stateless["rolling_options"])
    rolling_options["window_lengths"] = list(range(2, 2 + ROLLING_MAX_WINDOW_COUNT + 1))

    response = client.post("/analytics/risk/rolling-metrics", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_rolling_metrics_endpoint_rejects_too_many_stateless_observations() -> None:
    client = TestClient(app)
    payload = _volatility_only_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["returns"] = _return_points(ROLLING_MAX_STATELESS_OBSERVATIONS + 1)

    response = client.post("/analytics/risk/rolling-metrics", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_rolling_metrics_endpoint_rejects_unbounded_time_series_expansion() -> None:
    client = TestClient(app)
    payload = _volatility_only_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    window_count = 5
    period_count = 2
    observation_count = ROLLING_MAX_TIME_SERIES_POINTS // (window_count * period_count) + 1
    stateless["periods"] = _explicit_periods(period_count)
    stateless["returns"] = _return_points(observation_count)
    rolling_options = cast(dict[str, Any], stateless["rolling_options"])
    rolling_options["window_lengths"] = list(range(2, 2 + window_count))
    rolling_options["include_time_series"] = True

    response = client.post("/analytics/risk/rolling-metrics", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_rolling_metrics_endpoint_rejects_oversized_stateful_sourced_history() -> None:
    recorder = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=_return_rows(ROLLING_MAX_STATELESS_OBSERVATIONS + 1)
        )
    )
    with override_app_runtime(lotus_performance_client=recorder):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": ["ROLLING_VOLATILITY"],
                        "include_time_series": False,
                    },
                },
            },
        )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_INPUT"
    assert "sourced return observations exceed supported maximum" in body["message"]


def test_rolling_metrics_endpoint_stateless_marks_no_aligned_dependency_observations() -> None:
    client = TestClient(app)
    payload = _stateless_payload()
    stateless = payload["stateless_input"]
    assert isinstance(stateless, dict)
    stateless["benchmark_returns"] = [
        {"date": "2026-01-06", "value": 0.8},
        {"date": "2026-01-07", "value": -1.5},
    ]
    stateless["risk_free_returns"] = [
        {"date": "2026-01-06", "value": 0.01},
        {"date": "2026-01-07", "value": 0.01},
    ]
    stateless["rolling_options"] = {
        "window_lengths": [3],
        "metrics": ["ROLLING_SHARPE", "ROLLING_BETA"],
        "include_time_series": False,
    }
    response = client.post("/analytics/risk/rolling-metrics", json=payload)
    assert response.status_code == 200
    period = response.json()["results"]["YTD"]
    assert period["benchmark_series_count"] == 2
    assert period["aligned_benchmark_series_count"] == 0
    assert period["risk_free_series_count"] == 2
    assert period["aligned_risk_free_series_count"] == 0
    assert period["benchmark_context"] == {
        "requested": True,
        "available": True,
        "aligned": False,
        "reason": "NO_ALIGNED_OBSERVATIONS",
    }
    assert period["risk_free_context"] == {
        "requested": True,
        "available": True,
        "aligned": False,
        "reason": "NO_ALIGNED_OBSERVATIONS",
    }
    assert period["quality_flags"] == [
        "metric:ROLLING_BETA:alignment_empty",
        "metric:ROLLING_SHARPE:alignment_empty",
    ]


def test_rolling_metrics_endpoint_stateful_uses_runtime_client_overrides() -> None:
    _AutoWiredLotusPerformanceClient.calls = []
    with override_app_runtime(
        lotus_performance_client=_AutoWiredLotusPerformanceClient(),
        lotus_core_client=RecordingLotusCoreReferenceClient(
            risk_free_response=build_risk_free_series_response(
                points=[
                    {
                        "series_date": "2026-01-02",
                        "value": "0.0365",
                        "value_convention": "annualized_rate",
                    },
                    {
                        "series_date": "2026-01-05",
                        "value": "0.0365",
                        "value_convention": "annualized_rate",
                    },
                ]
            )
        ),
    ):
        client = TestClient(app)
        response = client.post(
            "/analytics/risk/rolling-metrics",
            headers={"X-Correlation-Id": "corr-rolling-runtime"},
            json={
                "input_mode": "stateful",
                "stateful_input": {
                    "portfolio_id": "DEMO_DPM_EUR_001",
                    "as_of_date": "2026-01-06",
                    "periods": [{"type": "YTD", "name": "YTD"}],
                    "rolling_options": {
                        "window_lengths": [2],
                        "metrics": ["ROLLING_VOLATILITY", "ROLLING_BETA"],
                    },
                },
            },
        )
        assert response.status_code == 200
        assert _AutoWiredLotusPerformanceClient.calls[0]["correlation_id"] == "corr-rolling-runtime"


def test_rolling_metrics_endpoint_rejects_simulation_mode_at_contract_boundary() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/rolling-metrics",
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-01-08",
                "periods": [{"type": "YTD"}],
            },
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
