from __future__ import annotations

from datetime import date
from typing import cast

import pandas as pd

from app.contracts.rolling import (
    RollingMetricSeriesContext,
    RollingMetricSeriesPoint,
    RollingMetricSummary,
)


def rolling_metric_summary(values: pd.Series, *, min_obs: int) -> RollingMetricSummary:
    clean = values.dropna()
    total_point_count = int(values.shape[0])
    warmup_point_count = min(total_point_count, max(min_obs - 1, 0))
    non_computed_point_count = total_point_count - int(clean.count())
    post_warmup_gap_point_count = max(non_computed_point_count - warmup_point_count, 0)
    if clean.empty:
        return RollingMetricSummary(
            total_point_count=total_point_count,
            computed_point_count=0,
            coverage_ratio=0.0,
            min_observations_required=min_obs,
            warmup_point_count=warmup_point_count,
            non_computed_point_count=non_computed_point_count,
            post_warmup_gap_point_count=post_warmup_gap_point_count,
            latest_observation_date=None,
            latest=None,
            average=None,
            minimum=None,
            maximum=None,
            p05=None,
            p50=None,
            p95=None,
        )
    return RollingMetricSummary(
        total_point_count=total_point_count,
        computed_point_count=int(clean.count()),
        coverage_ratio=float(clean.count() / total_point_count) if total_point_count else 0.0,
        min_observations_required=min_obs,
        warmup_point_count=warmup_point_count,
        non_computed_point_count=non_computed_point_count,
        post_warmup_gap_point_count=post_warmup_gap_point_count,
        latest_observation_date=cast(pd.Timestamp, clean.index[-1]).date(),
        latest=float(clean.iloc[-1]),
        average=float(clean.mean()),
        minimum=float(clean.min()),
        maximum=float(clean.max()),
        p05=float(clean.quantile(0.05)),
        p50=float(clean.quantile(0.50)),
        p95=float(clean.quantile(0.95)),
    )


def rolling_metric_series_points(
    metric_series_map: dict[str, pd.Series],
) -> list[RollingMetricSeriesPoint]:
    if not metric_series_map:
        return []

    points_by_date: dict[date, dict[str, float | None]] = {}
    for metric_name, series in metric_series_map.items():
        for index, observation in series.items():
            timestamp = cast(pd.Timestamp, index)
            day = timestamp.date()
            if day not in points_by_date:
                points_by_date[day] = {}
            numeric_observation = float(observation) if pd.notna(observation) else None
            points_by_date[day][metric_name] = numeric_observation

    ordered_dates = sorted(points_by_date.keys())
    return [
        RollingMetricSeriesPoint(date=day, metric_values=points_by_date[day])
        for day in ordered_dates
    ]


def rolling_metric_series_context(
    *,
    include_time_series: bool,
    metric_points: list[RollingMetricSeriesPoint] | None,
) -> RollingMetricSeriesContext:
    emitted_point_count = len(metric_points or [])
    if not include_time_series:
        return RollingMetricSeriesContext(
            requested=False,
            included=False,
            emitted_point_count=0,
            reason="OMITTED_BY_REQUEST",
        )
    if emitted_point_count == 0:
        return RollingMetricSeriesContext(
            requested=True,
            included=False,
            emitted_point_count=0,
            reason="NO_METRIC_SERIES",
        )
    return RollingMetricSeriesContext(
        requested=True,
        included=True,
        emitted_point_count=emitted_point_count,
        reason="INCLUDED",
    )
