import pandas as pd
import pytest

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownInputMode,
    DrawdownStatelessInput,
)
from app.services.drawdown_engine import _drawdown_summary, _duration_days, calculate_drawdown


def _request_payload() -> DrawdownStatelessInput:
    return DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -3.0},
                {"date": "2026-01-04", "value": -2.0},
                {"date": "2026-01-05", "value": 1.0},
                {"date": "2026-01-06", "value": 1.0},
                {"date": "2026-01-07", "value": 1.0},
                {"date": "2026-01-08", "value": 1.0},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.5},
                {"date": "2026-01-03", "value": -1.0},
                {"date": "2026-01-04", "value": -1.0},
                {"date": "2026-01-05", "value": 0.4},
                {"date": "2026-01-06", "value": 0.4},
                {"date": "2026-01-07", "value": 0.4},
                {"date": "2026-01-08", "value": 0.4},
            ],
        }
    )


def test_drawdown_engine_returns_period_summary_episode_and_underwater() -> None:
    response = calculate_drawdown(
        _request_payload(),
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate(
            {
                "include_underwater_series": True,
                "include_episode_list": True,
                "top_n_episodes": 5,
                "cdar_alpha": 0.95,
            }
        ),
    )
    period = response.results["YTD"]
    assert period.error is None
    assert period.portfolio_observation_count == 7
    assert period.benchmark_observation_count == 7
    assert period.summary is not None
    assert period.summary.max_drawdown is not None
    assert period.summary.max_drawdown < 0
    assert period.summary.max_drawdown_peak_date is not None
    assert period.summary.max_drawdown_trough_date is not None
    assert period.summary.time_under_water_days > 0
    assert period.summary.ulcer_index is not None
    assert period.episodes
    assert period.underwater_series is not None
    assert len(period.underwater_series) > 0
    assert period.relative_to_benchmark is not None
    assert period.relative_to_benchmark_context.requested is False
    assert period.relative_to_benchmark_context.applied is True
    assert period.relative_to_benchmark_context.reason == "APPLIED"
    assert period.relative_to_benchmark_context.aligned_observation_count == 7
    assert period.relative_to_benchmark.max_drawdown is not None
    assert period.relative_to_benchmark.days_to_trough is not None
    assert period.relative_to_benchmark.time_under_water_days >= 0
    assert response.metadata.include_underwater_series is True
    assert response.metadata.include_episode_list is True
    assert response.metadata.top_n_episodes == 5
    assert response.metadata.cdar_alpha == 0.95
    assert response.metadata.duration_unit == "BUSINESS_DAYS"
    assert response.metadata.include_benchmark is None
    assert response.metadata.missing_benchmark_policy is None


def test_drawdown_max_drawdown_matches_documented_decimal_output_contract() -> None:
    request = DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 10.0},
                {"date": "2026-01-05", "value": -20.0},
                {"date": "2026-01-06", "value": 30.0},
            ],
        }
    )

    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate(
            {
                "duration_unit": "BUSINESS_DAYS",
                "include_underwater_series": True,
                "include_episode_list": True,
            }
        ),
    )

    period = response.results["YTD"]
    assert period.error is None
    assert period.summary is not None
    assert period.summary.max_drawdown == pytest.approx(-0.2)
    assert str(period.summary.max_drawdown_peak_date) == "2026-01-02"
    assert str(period.summary.max_drawdown_trough_date) == "2026-01-05"
    assert str(period.summary.max_drawdown_recovery_date) == "2026-01-06"
    assert period.summary.is_recovered is True
    assert period.summary.days_to_trough == 1
    assert period.summary.days_to_recovery == 1
    assert period.summary.time_under_water_days == 1
    assert period.episodes[0].depth == pytest.approx(-0.2)
    assert str(period.episodes[0].peak_date) == "2026-01-02"
    assert str(period.episodes[0].trough_date) == "2026-01-05"
    assert str(period.episodes[0].recovery_date) == "2026-01-06"
    assert period.underwater_series is not None
    assert period.underwater_series[1].drawdown == pytest.approx(-0.2)


def test_drawdown_average_drawdown_matches_documented_decimal_output_contract() -> None:
    request = DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-07", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 5.0},
                {"date": "2026-01-05", "value": -10.0},
                {"date": "2026-01-06", "value": 2.0},
                {"date": "2026-01-07", "value": 4.0},
            ],
        }
    )

    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate(
            {
                "include_underwater_series": True,
                "include_episode_list": True,
                "top_n_episodes": 1,
                "minimum_episode_depth_bps": 500,
            }
        ),
    )

    period = response.results["YTD"]
    assert period.error is None
    assert period.summary is not None
    assert period.summary.average_drawdown == pytest.approx(-0.07576)
    assert period.summary.time_under_water_days == 3
    assert period.underwater_series is not None
    assert period.underwater_series[1].drawdown == pytest.approx(-0.1)
    assert period.underwater_series[2].drawdown == pytest.approx(-0.082)
    assert period.underwater_series[3].drawdown == pytest.approx(-0.04528)


def test_drawdown_engine_handles_empty_returns() -> None:
    request = DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [],
        }
    )
    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate({}),
    )
    assert response.results == {}
    assert response.metadata.include_episode_list is True
    assert response.metadata.include_benchmark is None


def test_drawdown_engine_respects_episode_threshold_and_top_n() -> None:
    response = calculate_drawdown(
        _request_payload(),
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate(
            {
                "include_episode_list": True,
                "top_n_episodes": 1,
                "minimum_episode_depth_bps": 10,
            }
        ),
    )
    period = response.results["YTD"]
    assert len(period.episodes) <= 1


def test_drawdown_engine_covers_recovered_episode_and_calendar_duration() -> None:
    request = DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -2.0},
                {"date": "2026-01-04", "value": 2.5},
                {"date": "2026-01-05", "value": 0.2},
                {"date": "2026-01-06", "value": 0.1},
            ],
        }
    )
    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate(
            {"duration_unit": "CALENDAR_DAYS", "include_episode_list": True}
        ),
    )
    period = response.results["YTD"]
    assert period.summary is not None
    assert period.episodes
    assert period.episodes[0].is_recovered is True
    assert period.episodes[0].days_to_recovery is not None


def test_drawdown_engine_sets_period_error_when_window_has_no_observations() -> None:
    request = DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-10", "net_or_gross": "NET"},
            "periods": [
                {
                    "type": "EXPLICIT",
                    "name": "empty",
                    "from_date": "2026-01-08",
                    "to_date": "2026-01-09",
                }
            ],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -2.0},
            ],
        }
    )
    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate({}),
        include_benchmark=True,
    )
    assert response.results["empty"].error == "Insufficient data"
    assert response.results["empty"].portfolio_observation_count == 0
    assert response.results["empty"].benchmark_observation_count == 0
    assert response.results["empty"].relative_to_benchmark_context.requested is True
    assert response.results["empty"].relative_to_benchmark_context.applied is False
    assert response.results["empty"].relative_to_benchmark_context.reason == "BENCHMARK_UNAVAILABLE"


def test_drawdown_engine_reports_unapplied_relative_context_when_benchmark_missing() -> None:
    request = DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -3.0},
            ],
            "benchmark_returns": [],
        }
    )
    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate({}),
        include_benchmark=True,
    )
    period = response.results["YTD"]
    assert period.portfolio_observation_count == 2
    assert period.benchmark_observation_count == 0
    assert period.relative_to_benchmark is None
    assert period.relative_to_benchmark_context.requested is True
    assert period.relative_to_benchmark_context.applied is False
    assert period.relative_to_benchmark_context.reason == "BENCHMARK_UNAVAILABLE"
    assert period.relative_to_benchmark_context.aligned_observation_count == 0


def test_drawdown_engine_reports_no_aligned_observations_reason() -> None:
    request = DrawdownStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -3.0},
            ],
            "benchmark_returns": [
                {"date": "2026-01-06", "value": 0.4},
                {"date": "2026-01-07", "value": 0.4},
            ],
        }
    )
    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions.model_validate({}),
        include_benchmark=True,
    )
    period = response.results["YTD"]
    assert period.portfolio_observation_count == 2
    assert period.benchmark_observation_count == 2
    assert period.relative_to_benchmark is None
    assert period.relative_to_benchmark_context.requested is True
    assert period.relative_to_benchmark_context.applied is False
    assert period.relative_to_benchmark_context.reason == "NO_ALIGNED_OBSERVATIONS"
    assert period.relative_to_benchmark_context.aligned_observation_count == 0


def test_drawdown_engine_empty_summary_and_duration_guard_branches() -> None:
    summary, episodes = _drawdown_summary(
        pd.Series(dtype=float),
        alpha=0.95,
        duration_unit="BUSINESS_DAYS",
    )
    assert summary.max_drawdown is None
    assert episodes == []
    assert (
        _duration_days(
            pd.Timestamp("2026-01-03").date(),
            pd.Timestamp("2026-01-02").date(),
            unit="BUSINESS_DAYS",
        )
        == 0
    )
    assert (
        _duration_days(
            pd.Timestamp("2026-01-02").date(),
            pd.Timestamp("2026-01-05").date(),
            unit="CALENDAR_DAYS",
        )
        == 3
    )
