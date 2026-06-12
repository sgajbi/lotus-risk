from __future__ import annotations

import datetime as dt
from typing import cast

import pandas as pd

from app.contracts.attribution import (
    AttributionOptions,
    HistoricalAttributionPeriodResult,
    HistoricalAttributionStatelessInput,
)
from app.contracts.risk import RiskRequestPeriod
from app.services.attribution_decomposition import (
    AttributionSourceFrames,
    build_period_attribution_sets,
    window_returns,
)
from app.services.risk.period_resolution import resolve_period


def period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


def resolved_period_window(
    *,
    period: RiskRequestPeriod,
    request: HistoricalAttributionStatelessInput,
    open_date: pd.Timestamp,
) -> tuple[dt.date, dt.date, pd.Timestamp, pd.Timestamp]:
    start_date, end_date = resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date.date(),
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    return start_date, end_date, pd.Timestamp(start_date), pd.Timestamp(end_date)


def period_returns_series(
    *,
    frames: AttributionSourceFrames,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    return window_returns(frames.returns_df, start, end) / 100.0


def period_benchmark_series(
    *,
    frames: AttributionSourceFrames,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    if frames.benchmark_df.empty:
        return pd.Series(dtype="float64")
    return window_returns(frames.benchmark_df, start, end) / 100.0


def insufficient_attribution_result(
    *,
    start_date: dt.date,
    end_date: dt.date,
) -> HistoricalAttributionPeriodResult:
    return HistoricalAttributionPeriodResult(
        start_date=start_date,
        end_date=end_date,
        attribution_sets=[],
        error="Insufficient data",
    )


def attribution_period_result(
    *,
    start_date: dt.date,
    end_date: dt.date,
    options: AttributionOptions,
    frames: AttributionSourceFrames,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> HistoricalAttributionPeriodResult:
    return HistoricalAttributionPeriodResult(
        start_date=start_date,
        end_date=end_date,
        attribution_sets=build_period_attribution_sets(
            options=options,
            frames=frames,
            returns_series=returns_series,
            benchmark_series=benchmark_series,
            start=start,
            end=end,
        ),
        error=None,
    )


def calculate_period_attribution(
    *,
    period: RiskRequestPeriod,
    request: HistoricalAttributionStatelessInput,
    frames: AttributionSourceFrames,
    open_timestamp: pd.Timestamp,
    options: AttributionOptions,
) -> tuple[str, HistoricalAttributionPeriodResult]:
    start_date, end_date, start, end = resolved_period_window(
        period=period,
        request=request,
        open_date=open_timestamp,
    )
    name = period_name(period)
    returns_series = period_returns_series(frames=frames, start=start, end=end)
    benchmark_series = period_benchmark_series(
        frames=frames,
        start=start,
        end=end,
    )
    if len(returns_series.dropna()) < 2:
        return name, insufficient_attribution_result(
            start_date=start_date,
            end_date=end_date,
        )

    return name, attribution_period_result(
        start_date=start_date,
        end_date=end_date,
        options=options,
        frames=frames,
        returns_series=returns_series,
        benchmark_series=benchmark_series,
        start=start,
        end=end,
    )


def historical_attribution_period_results(
    *,
    request: HistoricalAttributionStatelessInput,
    frames: AttributionSourceFrames,
    options: AttributionOptions,
) -> dict[str, HistoricalAttributionPeriodResult]:
    open_timestamp = cast(pd.Timestamp, frames.returns_df.index.min())
    results: dict[str, HistoricalAttributionPeriodResult] = {}
    for period in request.periods:
        name, period_result = calculate_period_attribution(
            period=period,
            request=request,
            frames=frames,
            open_timestamp=open_timestamp,
            options=options,
        )
        results[name] = period_result
    return results


__all__ = [
    "attribution_period_result",
    "calculate_period_attribution",
    "historical_attribution_period_results",
    "insufficient_attribution_result",
    "period_benchmark_series",
    "period_name",
    "period_returns_series",
    "resolved_period_window",
]
