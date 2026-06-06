from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from app.contracts.rolling import RollingOptions, RollingWindowResult
from app.services.rolling_engine_models import (
    RollingPeriodSeries,
    RollingPeriodWindowAggregate,
    RollingWindowCalculation,
)
from app.services.rolling_metric_series import (
    RollingMetricCalculation,
    calculate_rolling_metric_values,
    min_observations,
    rolling_metric_series_context,
    rolling_metric_series_points,
    rolling_metric_summary,
)


@dataclass
class _RollingWindowMetricAggregate:
    metric_series_map: dict[str, pd.Series] = field(default_factory=dict)
    quality_flags: set[str] = field(default_factory=set)
    aligned_benchmark_series_count: int = 0
    aligned_risk_free_series_count: int = 0

    def add_metric(self, metric_name: str, calculation: RollingMetricCalculation) -> None:
        self.metric_series_map[metric_name] = calculation.values
        self.quality_flags.update(calculation.quality_flags)
        self.aligned_benchmark_series_count = max(
            self.aligned_benchmark_series_count,
            calculation.aligned_benchmark_series_count,
        )
        self.aligned_risk_free_series_count = max(
            self.aligned_risk_free_series_count,
            calculation.aligned_risk_free_series_count,
        )


def calculate_window_result(
    period_series: RollingPeriodSeries,
    *,
    requested_metrics: Sequence[str],
    options: RollingOptions,
    window_length: int,
) -> RollingWindowCalculation:
    min_obs = min_observations(window_length, options.min_observations_policy)
    aggregate = _calculate_window_metric_aggregate(
        period_series,
        requested_metrics=requested_metrics,
        options=options,
        window_length=window_length,
        min_obs=min_obs,
    )

    summaries = {
        metric_name: rolling_metric_summary(series, min_obs=min_obs)
        for metric_name, series in aggregate.metric_series_map.items()
    }
    metric_points = (
        rolling_metric_series_points(aggregate.metric_series_map)
        if options.include_time_series
        else None
    )
    return RollingWindowCalculation(
        window_result=RollingWindowResult(
            window_length=window_length,
            metric_summaries=summaries,
            metric_series=metric_points,
            metric_series_context=rolling_metric_series_context(
                include_time_series=options.include_time_series,
                metric_points=metric_points,
            ),
        ),
        quality_flags=aggregate.quality_flags,
        aligned_benchmark_series_count=aggregate.aligned_benchmark_series_count,
        aligned_risk_free_series_count=aggregate.aligned_risk_free_series_count,
    )


def _calculate_window_metric_aggregate(
    period_series: RollingPeriodSeries,
    *,
    requested_metrics: Sequence[str],
    options: RollingOptions,
    window_length: int,
    min_obs: int,
) -> _RollingWindowMetricAggregate:
    aggregate = _RollingWindowMetricAggregate()
    for metric_name in requested_metrics:
        calculation = calculate_rolling_metric_values(
            metric_name,
            portfolio_decimal=period_series.portfolio_decimal,
            benchmark_decimal=period_series.benchmark_decimal,
            risk_free_decimal=period_series.risk_free_decimal,
            window_length=window_length,
            annualization_basis=options.annualization_basis,
            min_obs=min_obs,
        )
        aggregate.add_metric(metric_name, calculation)

    return aggregate


def rolling_period_window_aggregate(
    period_series: RollingPeriodSeries,
    *,
    options: RollingOptions,
    requested_metrics: Sequence[str],
) -> RollingPeriodWindowAggregate:
    window_results: list[RollingWindowResult] = []
    period_flags: set[str] = set()
    aligned_benchmark_series_count = 0
    aligned_risk_free_series_count = 0

    for window_length in options.window_lengths:
        calculation = calculate_window_result(
            period_series,
            requested_metrics=requested_metrics,
            options=options,
            window_length=window_length,
        )
        window_results.append(calculation.window_result)
        period_flags.update(calculation.quality_flags)
        aligned_benchmark_series_count = max(
            aligned_benchmark_series_count,
            calculation.aligned_benchmark_series_count,
        )
        aligned_risk_free_series_count = max(
            aligned_risk_free_series_count,
            calculation.aligned_risk_free_series_count,
        )

    return RollingPeriodWindowAggregate(
        window_results=window_results,
        quality_flags=period_flags,
        aligned_benchmark_series_count=aligned_benchmark_series_count,
        aligned_risk_free_series_count=aligned_risk_free_series_count,
    )
