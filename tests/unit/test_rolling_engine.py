import pandas as pd
import pytest

from app.contracts.rolling import RollingInputMode, RollingStatelessInput
from app.services.rolling_engine import calculate_rolling_metrics
from app.services.rolling_metric_series import calculate_rolling_metric_values


def _base_input() -> RollingStatelessInput:
    return RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -2.0},
                {"date": "2026-01-04", "value": 0.5},
                {"date": "2026-01-05", "value": 1.2},
                {"date": "2026-01-06", "value": -0.7},
                {"date": "2026-01-07", "value": 0.4},
                {"date": "2026-01-08", "value": 0.3},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-03", "value": -1.5},
                {"date": "2026-01-04", "value": 0.4},
                {"date": "2026-01-05", "value": 1.0},
                {"date": "2026-01-06", "value": -0.6},
                {"date": "2026-01-07", "value": 0.2},
                {"date": "2026-01-08", "value": 0.2},
            ],
            "risk_free_returns": [
                {"date": "2026-01-02", "value": 0.01},
                {"date": "2026-01-03", "value": 0.01},
                {"date": "2026-01-04", "value": 0.01},
                {"date": "2026-01-05", "value": 0.01},
                {"date": "2026-01-06", "value": 0.01},
                {"date": "2026-01-07", "value": 0.01},
                {"date": "2026-01-08", "value": 0.01},
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
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "include_time_series": True,
            },
        }
    )


def test_rolling_engine_returns_window_results_and_metadata() -> None:
    response = calculate_rolling_metrics(_base_input(), input_mode=RollingInputMode.STATELESS)
    assert response.input_mode == RollingInputMode.STATELESS
    assert response.metadata.methodology_version == "rolling_metrics.v1"
    period = response.results["YTD"]
    assert period.error is None
    assert period.series_count == 7
    assert len(period.window_results) == 1

    window = period.window_results[0]
    assert window.window_length == 3
    assert "ROLLING_VOLATILITY" in window.metric_summaries
    assert window.metric_summaries["ROLLING_VOLATILITY"].latest is not None
    assert window.metric_summaries["ROLLING_MAX_DRAWDOWN"].minimum is not None
    assert window.metric_series is not None
    assert len(window.metric_series) > 0


def test_rolling_engine_preserves_dependency_alignment_counts() -> None:
    response = calculate_rolling_metrics(_base_input(), input_mode=RollingInputMode.STATELESS)

    period = response.results["YTD"]

    assert period.benchmark_series_count == 7
    assert period.aligned_benchmark_series_count == 7
    assert period.risk_free_series_count == 7
    assert period.aligned_risk_free_series_count == 7
    assert period.benchmark_context.aligned is True
    assert period.risk_free_context.aligned is True


def test_rolling_metric_dispatch_rejects_unknown_metric() -> None:
    series = pd.Series([0.01, 0.02, -0.01])

    with pytest.raises(ValueError, match="Unsupported rolling metric"):
        calculate_rolling_metric_values(
            "ROLLING_UNKNOWN",
            portfolio_decimal=series,
            benchmark_decimal=pd.Series(dtype="float64"),
            risk_free_decimal=pd.Series(dtype="float64"),
            window_length=3,
            annualization_basis=252,
            min_obs=3,
        )


def test_rolling_volatility_matches_documented_decimal_methodology() -> None:
    payload = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-01", "value": 1.0},
                {"date": "2026-01-02", "value": -2.0},
                {"date": "2026-01-03", "value": 1.5},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_VOLATILITY"],
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "include_time_series": True,
            },
        }
    )

    response = calculate_rolling_metrics(payload, input_mode=RollingInputMode.STATELESS)

    window = response.results["YTD"].window_results[0]
    summary = window.metric_summaries["ROLLING_VOLATILITY"]

    assert summary.latest == pytest.approx(0.3004995840263344)
    assert summary.latest_observation_date is not None
    assert summary.latest_observation_date.isoformat() == "2026-01-03"
    assert summary.min_observations_required == 3
    assert summary.warmup_point_count == 2
    assert summary.computed_point_count == 1

    assert window.metric_series is not None
    latest_point = window.metric_series[-1]
    assert latest_point.date.isoformat() == "2026-01-03"
    assert latest_point.metric_values["ROLLING_VOLATILITY"] == pytest.approx(summary.latest)


def test_rolling_tracking_error_matches_documented_decimal_methodology() -> None:
    response = calculate_rolling_metrics(_base_input(), input_mode=RollingInputMode.STATELESS)

    window = response.results["YTD"].window_results[0]
    summary = window.metric_summaries["ROLLING_TRACKING_ERROR"]

    assert summary.latest == pytest.approx(0.02424871130596428)
    assert summary.latest_observation_date is not None
    assert summary.latest_observation_date.isoformat() == "2026-01-08"
    assert summary.min_observations_required == 3
    assert summary.warmup_point_count == 2
    assert summary.computed_point_count == 5

    assert window.metric_series is not None
    latest_point = window.metric_series[-1]
    assert latest_point.date.isoformat() == "2026-01-08"
    assert latest_point.metric_values["ROLLING_TRACKING_ERROR"] == pytest.approx(summary.latest)


def test_rolling_information_ratio_matches_documented_decimal_methodology() -> None:
    response = calculate_rolling_metrics(_base_input(), input_mode=RollingInputMode.STATELESS)

    period = response.results["YTD"]
    window = period.window_results[0]
    summary = window.metric_summaries["ROLLING_INFORMATION_RATIO"]

    assert period.quality_flags == []
    assert summary.latest == pytest.approx(6.928203230275508)
    assert summary.latest_observation_date is not None
    assert summary.latest_observation_date.isoformat() == "2026-01-08"
    assert summary.min_observations_required == 3
    assert summary.warmup_point_count == 2
    assert summary.computed_point_count == 5

    assert window.metric_series is not None
    latest_point = window.metric_series[-1]
    assert latest_point.date.isoformat() == "2026-01-08"
    assert latest_point.metric_values["ROLLING_INFORMATION_RATIO"] == pytest.approx(summary.latest)


def test_rolling_sharpe_matches_documented_decimal_methodology() -> None:
    payload = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-01", "value": 0.50},
                {"date": "2026-01-02", "value": 0.20},
                {"date": "2026-01-03", "value": -0.10},
            ],
            "risk_free_returns": [
                {"date": "2026-01-01", "value": 0.01},
                {"date": "2026-01-02", "value": 0.01},
                {"date": "2026-01-03", "value": 0.01},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_SHARPE"],
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "include_time_series": True,
            },
        }
    )

    response = calculate_rolling_metrics(payload, input_mode=RollingInputMode.STATELESS)

    period = response.results["YTD"]
    window = period.window_results[0]
    summary = window.metric_summaries["ROLLING_SHARPE"]

    assert period.quality_flags == []
    assert summary.latest == pytest.approx(10.053854982045443)
    assert summary.latest_observation_date is not None
    assert summary.latest_observation_date.isoformat() == "2026-01-03"
    assert summary.min_observations_required == 3
    assert summary.warmup_point_count == 2
    assert summary.computed_point_count == 1

    assert window.metric_series is not None
    latest_point = window.metric_series[-1]
    assert latest_point.date.isoformat() == "2026-01-03"
    assert latest_point.metric_values["ROLLING_SHARPE"] == pytest.approx(summary.latest)


def test_rolling_beta_matches_documented_decimal_methodology() -> None:
    payload = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-01", "value": 1.50},
                {"date": "2026-01-02", "value": -3.00},
                {"date": "2026-01-03", "value": 2.25},
            ],
            "benchmark_returns": [
                {"date": "2026-01-01", "value": 1.00},
                {"date": "2026-01-02", "value": -2.00},
                {"date": "2026-01-03", "value": 1.50},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_BETA"],
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "include_time_series": True,
            },
        }
    )

    response = calculate_rolling_metrics(payload, input_mode=RollingInputMode.STATELESS)

    period = response.results["YTD"]
    window = period.window_results[0]
    summary = window.metric_summaries["ROLLING_BETA"]

    assert period.quality_flags == []
    assert summary.latest == pytest.approx(1.5)
    assert summary.latest_observation_date is not None
    assert summary.latest_observation_date.isoformat() == "2026-01-03"
    assert summary.min_observations_required == 3
    assert summary.warmup_point_count == 2
    assert summary.computed_point_count == 1

    assert window.metric_series is not None
    latest_point = window.metric_series[-1]
    assert latest_point.date.isoformat() == "2026-01-03"
    assert latest_point.metric_values["ROLLING_BETA"] == pytest.approx(summary.latest)


def test_rolling_max_drawdown_matches_documented_decimal_methodology() -> None:
    payload = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-01", "value": 5.00},
                {"date": "2026-01-02", "value": -10.00},
                {"date": "2026-01-03", "value": 2.00},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_MAX_DRAWDOWN"],
                "annualization_basis": 252,
                "min_observations_policy": "STRICT",
                "include_time_series": True,
            },
        }
    )

    response = calculate_rolling_metrics(payload, input_mode=RollingInputMode.STATELESS)

    period = response.results["YTD"]
    window = period.window_results[0]
    summary = window.metric_summaries["ROLLING_MAX_DRAWDOWN"]

    assert period.quality_flags == []
    assert summary.latest == pytest.approx(-0.1)
    assert summary.latest_observation_date is not None
    assert summary.latest_observation_date.isoformat() == "2026-01-03"
    assert summary.min_observations_required == 3
    assert summary.warmup_point_count == 2
    assert summary.computed_point_count == 1

    assert window.metric_series is not None
    latest_point = window.metric_series[-1]
    assert latest_point.date.isoformat() == "2026-01-03"
    assert latest_point.metric_values["ROLLING_MAX_DRAWDOWN"] == pytest.approx(summary.latest)


def test_rolling_engine_returns_period_error_when_insufficient_period_data() -> None:
    payload = {
        "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
        "periods": [
            {
                "type": "EXPLICIT",
                "name": "SHORT",
                "from_date": "2026-01-08",
                "to_date": "2026-01-08",
            }
        ],
        "returns": [
            {"date": "2026-01-08", "value": 0.3},
        ],
        "rolling_options": {
            "window_lengths": [3],
            "metrics": ["ROLLING_VOLATILITY"],
        },
    }
    request = RollingStatelessInput.model_validate(payload)
    response = calculate_rolling_metrics(request, input_mode=RollingInputMode.STATELESS)
    period = response.results["SHORT"]
    assert period.error == "Insufficient data"
    assert period.window_results == []


def test_rolling_engine_reports_benchmark_no_aligned_observations() -> None:
    request = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-05", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-01", "value": 0.5},
                {"date": "2026-01-03", "value": -0.2},
                {"date": "2026-01-05", "value": 0.1},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.4},
                {"date": "2026-01-04", "value": -0.1},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_BETA"],
                "min_observations_policy": "STRICT",
            },
        }
    )

    response = calculate_rolling_metrics(request, input_mode=RollingInputMode.STATELESS)
    context = response.results["YTD"].benchmark_context

    assert context.requested is True
    assert context.available is True
    assert context.aligned is False
    assert context.reason == "NO_ALIGNED_OBSERVATIONS"


def test_rolling_engine_reports_risk_free_unavailable_for_sharpe() -> None:
    request = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-03", "value": -0.1},
            ],
            "risk_free_returns": [{"date": "2026-01-03", "value": 0.01}],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_SHARPE"],
                "min_observations_policy": "STRICT",
            },
        }
    )

    response = calculate_rolling_metrics(request, input_mode=RollingInputMode.STATELESS)
    context = response.results["YTD"].risk_free_context

    assert context.requested is True
    assert context.available is False
    assert context.aligned is False
    assert context.reason == "RISK_FREE_UNAVAILABLE"


def test_rolling_engine_handles_empty_return_series() -> None:
    request = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_VOLATILITY"],
            },
        }
    )
    response = calculate_rolling_metrics(request, input_mode=RollingInputMode.STATELESS)
    assert response.results == {}


def test_rolling_engine_emits_quality_flag_for_zero_benchmark_variance() -> None:
    request = RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 0.5},
                {"date": "2026-01-03", "value": -0.2},
                {"date": "2026-01-04", "value": 0.1},
                {"date": "2026-01-05", "value": 0.3},
                {"date": "2026-01-06", "value": -0.1},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.0},
                {"date": "2026-01-03", "value": 0.0},
                {"date": "2026-01-04", "value": 0.0},
                {"date": "2026-01-05", "value": 0.0},
                {"date": "2026-01-06", "value": 0.0},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": ["ROLLING_BETA"],
                "min_observations_policy": "STRICT",
            },
        }
    )

    response = calculate_rolling_metrics(request, input_mode=RollingInputMode.STATELESS)
    period = response.results["YTD"]
    assert "metric:ROLLING_BETA:benchmark_variance_zero" in period.quality_flags


def test_every_rolling_metric_states_its_unit_semantics() -> None:
    from typing import get_args

    from app.contracts.rolling import ROLLING_METRIC_UNIT_SEMANTICS, RollingMetric

    stated = set(ROLLING_METRIC_UNIT_SEMANTICS)
    vocabulary = set(get_args(RollingMetric))
    assert stated == vocabulary, (
        "A rolling metric without stated unit semantics is unreadable downstream; "
        f"missing={sorted(vocabulary - stated)}, orphaned={sorted(stated - vocabulary)}"
    )
    assert set(ROLLING_METRIC_UNIT_SEMANTICS.values()) <= {"decimal_ratio", "unitless"}


def test_rolling_response_metadata_states_unit_semantics_for_requested_metrics() -> None:
    response = calculate_rolling_metrics(_base_input(), input_mode=RollingInputMode.STATELESS)

    assert response.metadata.metric_unit_semantics == {
        "ROLLING_VOLATILITY": "decimal_ratio",
        "ROLLING_SHARPE": "unitless",
        "ROLLING_BETA": "unitless",
        "ROLLING_TRACKING_ERROR": "decimal_ratio",
        "ROLLING_INFORMATION_RATIO": "unitless",
        "ROLLING_MAX_DRAWDOWN": "decimal_ratio",
    }


def test_metadata_refuses_a_unit_map_that_does_not_match_requested_metrics() -> None:
    """The rolling twin of the attribution equality guard (#263): a subset
    leaves a requested value unreadable, a superset states units for values
    the response does not carry, empty-while-requesting is the mock drift
    the #262 review flagged, and a contradicted unit is a 100x lie."""

    from app.contracts.rolling_metadata_outputs import RollingMetadata

    def metadata(**overrides: object) -> RollingMetadata:
        fields: dict[str, object] = {
            "request_fingerprint": "fp",
            "annualization_basis": 252,
            "metric_unit_semantics": {"ROLLING_VOLATILITY": "decimal_ratio"},
            "requested_metrics": ["ROLLING_VOLATILITY"],
            "alignment_policy": "INNER_JOIN",
            "min_observations_policy": "STRICT",
            "include_time_series": False,
            "benchmark_context": {"requested": False, "requested_metrics": []},
            "risk_free_context": {"requested": False, "requested_metrics": []},
        }
        fields.update(overrides)
        return RollingMetadata(**fields)  # type: ignore[arg-type]

    assert metadata().metric_unit_semantics == {"ROLLING_VOLATILITY": "decimal_ratio"}

    # An empty map is refused by the schema bound before the equality check runs.
    with pytest.raises(ValueError, match="at least 1 item"):
        metadata(metric_unit_semantics={})

    # A non-empty map for the wrong metric hits the equality check: both the
    # missing and the surplus side are named.
    with pytest.raises(ValueError, match="missing=..ROLLING_VOLATILITY"):
        metadata(metric_unit_semantics={"ROLLING_BETA": "unitless"})

    with pytest.raises(ValueError, match="surplus=..ROLLING_BETA"):
        metadata(
            metric_unit_semantics={
                "ROLLING_VOLATILITY": "decimal_ratio",
                "ROLLING_BETA": "unitless",
            }
        )

    # A unit that contradicts the canonical source-owned map is refused even
    # when the key set matches exactly.
    with pytest.raises(ValueError, match="contradicts the canonical source-owned units"):
        metadata(metric_unit_semantics={"ROLLING_VOLATILITY": "unitless"})

    # And an unbounded key never enters: the typed key refuses it at the schema.
    with pytest.raises(ValueError, match="ROLLING_FICTIONAL"):
        metadata(
            metric_unit_semantics={"ROLLING_FICTIONAL": "decimal_ratio"},
            requested_metrics=["ROLLING_FICTIONAL"],
        )
