from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from typing import cast
from collections.abc import Sequence

import numpy as np
import pandas as pd

from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingInputMode,
    RollingBenchmarkContext,
    RollingMetadata,
    RollingMetricSeriesPoint,
    RollingMetricSeriesContext,
    RollingMetricSummary,
    RollingOptions,
    RollingPeriodResult,
    RollingRequestDependencyContext,
    RollingRiskFreeContext,
    RollingResponse,
    RollingStatelessInput,
    RollingWindowResult,
)
from app.contracts.risk import ReturnPoint, RiskCalculationSupportability, RiskRequestPeriod
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_period_results,
)
from app.services.risk import helpers as risk_helpers


ROLLING_SHARPE_METRIC = "ROLLING_SHARPE"
ROLLING_MAX_DRAWDOWN_METRIC = "ROLLING_MAX_DRAWDOWN"


@dataclass(frozen=True)
class _RollingInputFrames:
    portfolio: pd.DataFrame
    benchmark: pd.DataFrame
    risk_free: pd.DataFrame


@dataclass(frozen=True)
class _RollingPeriodSeries:
    name: str
    start: date
    end: date
    portfolio_pp: pd.Series
    portfolio_decimal: pd.Series
    benchmark_decimal: pd.Series
    risk_free_decimal: pd.Series


@dataclass(frozen=True)
class _RollingWindowCalculation:
    window_result: RollingWindowResult
    quality_flags: set[str]
    aligned_benchmark_series_count: int
    aligned_risk_free_series_count: int


def _build_returns_df(returns: list[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in returns])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


def _filter_period(df: pd.DataFrame, *, start: date, end: date) -> pd.Series:
    return df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)), "value"]


def _min_observations(window_length: int, policy: str) -> int:
    if policy == "ALLOW_PARTIAL":
        return 2
    return window_length


def _rolling_max_drawdown(window_decimal_returns: np.ndarray) -> float:
    wealth = np.cumprod(1.0 + window_decimal_returns)
    running_peak = np.maximum.accumulate(wealth)
    drawdown = wealth / running_peak - 1.0
    return float(np.min(drawdown))


def _summary(values: pd.Series, *, min_obs: int) -> RollingMetricSummary:
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


def _rolling_volatility(
    series_decimal: pd.Series, *, window_length: int, annualization_basis: int, min_obs: int
) -> pd.Series:
    return series_decimal.rolling(window=window_length, min_periods=min_obs).std(ddof=1) * sqrt(
        annualization_basis
    )


def _rolling_sharpe(
    portfolio_decimal: pd.Series,
    risk_free_decimal: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str], int]:
    aligned = pd.merge(
        portfolio_decimal.to_frame("portfolio"),
        risk_free_decimal.to_frame("risk_free"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    if aligned.empty:
        return pd.Series(dtype="float64"), ["metric:ROLLING_SHARPE:alignment_empty"], 0

    active = aligned["portfolio"] - aligned["risk_free"]
    roll_mean = active.rolling(window=window_length, min_periods=min_obs).mean()
    roll_std = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1)
    sharpe = (roll_mean / roll_std) * sqrt(annualization_basis)
    sharpe = sharpe.replace([np.inf, -np.inf], np.nan)
    flags: list[str] = []
    if roll_std.dropna().eq(0).any():
        flags.append("metric:ROLLING_SHARPE:zero_volatility_window")
    return sharpe, flags, int(aligned.shape[0])


def _rolling_benchmark_metrics(
    metric_name: str,
    portfolio_decimal: pd.Series,
    benchmark_decimal: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str], int]:
    aligned = pd.merge(
        portfolio_decimal.to_frame("portfolio"),
        benchmark_decimal.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    if aligned.empty:
        return pd.Series(dtype="float64"), [f"metric:{metric_name}:alignment_empty"], 0

    portfolio = aligned["portfolio"]
    benchmark = aligned["benchmark"]

    if metric_name == "ROLLING_TRACKING_ERROR":
        active = portfolio - benchmark
        result = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1) * sqrt(
            annualization_basis
        )
        return result, [], int(aligned.shape[0])

    if metric_name == "ROLLING_INFORMATION_RATIO":
        active = portfolio - benchmark
        roll_mean = active.rolling(window=window_length, min_periods=min_obs).mean()
        roll_std = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1)
        result = (roll_mean / roll_std) * sqrt(annualization_basis)
        result = result.replace([np.inf, -np.inf], np.nan)
        flags: list[str] = []
        if roll_std.dropna().eq(0).any():
            flags.append("metric:ROLLING_INFORMATION_RATIO:zero_tracking_error_window")
        return result, flags, int(aligned.shape[0])

    if metric_name == "ROLLING_BETA":
        roll_cov = portfolio.rolling(window=window_length, min_periods=min_obs).cov(benchmark)
        roll_var = benchmark.rolling(window=window_length, min_periods=min_obs).var(ddof=1)
        result = roll_cov / roll_var
        result = result.replace([np.inf, -np.inf], np.nan)
        flags = []
        if roll_var.dropna().eq(0).any():
            flags.append("metric:ROLLING_BETA:benchmark_variance_zero")
        return result, flags, int(aligned.shape[0])

    raise ValueError(f"Unsupported rolling benchmark metric: {metric_name}")


def _rolling_max_drawdown_metric(
    series_decimal: pd.Series, *, window_length: int, min_obs: int
) -> pd.Series:
    return series_decimal.rolling(window=window_length, min_periods=min_obs).apply(
        _rolling_max_drawdown,
        raw=True,
    )


def _window_series_points(
    metric_series_map: dict[str, pd.Series],
) -> list[RollingMetricSeriesPoint]:
    if not metric_series_map:
        return []

    points_by_date: dict[date, dict[str, float | None]] = {}
    for metric_name, series in metric_series_map.items():
        for index, value in series.items():
            timestamp = cast(pd.Timestamp, index)
            day = timestamp.date()
            if day not in points_by_date:
                points_by_date[day] = {}
            points_by_date[day][metric_name] = float(value) if pd.notna(value) else None

    ordered_dates = sorted(points_by_date.keys())
    return [
        RollingMetricSeriesPoint(date=day, metric_values=points_by_date[day])
        for day in ordered_dates
    ]


def _benchmark_context(
    requested_metrics: Sequence[str],
    benchmark_series_count: int,
    aligned_benchmark_series_count: int,
) -> RollingBenchmarkContext:
    requested = any(metric in ROLLING_BENCHMARK_METRICS for metric in requested_metrics)
    if not requested:
        return RollingBenchmarkContext(
            requested=False,
            available=False,
            aligned=False,
            reason="NOT_REQUESTED",
        )
    if benchmark_series_count == 0:
        return RollingBenchmarkContext(
            requested=True,
            available=False,
            aligned=False,
            reason="BENCHMARK_UNAVAILABLE",
        )
    if aligned_benchmark_series_count == 0:
        return RollingBenchmarkContext(
            requested=True,
            available=True,
            aligned=False,
            reason="NO_ALIGNED_OBSERVATIONS",
        )
    return RollingBenchmarkContext(
        requested=True,
        available=True,
        aligned=True,
        reason="APPLIED",
    )


def _risk_free_context(
    requested_metrics: Sequence[str],
    risk_free_series_count: int,
    aligned_risk_free_series_count: int,
) -> RollingRiskFreeContext:
    requested = ROLLING_SHARPE_METRIC in requested_metrics
    if not requested:
        return RollingRiskFreeContext(
            requested=False,
            available=False,
            aligned=False,
            reason="NOT_REQUESTED",
        )
    if risk_free_series_count == 0:
        return RollingRiskFreeContext(
            requested=True,
            available=False,
            aligned=False,
            reason="RISK_FREE_UNAVAILABLE",
        )
    if aligned_risk_free_series_count == 0:
        return RollingRiskFreeContext(
            requested=True,
            available=True,
            aligned=False,
            reason="NO_ALIGNED_OBSERVATIONS",
        )
    return RollingRiskFreeContext(
        requested=True,
        available=True,
        aligned=True,
        reason="APPLIED",
    )


def _request_dependency_context(
    requested_metrics: Sequence[str], dependency_metrics: set[str]
) -> RollingRequestDependencyContext:
    requested = [metric for metric in requested_metrics if metric in dependency_metrics]
    return RollingRequestDependencyContext(
        requested=bool(requested),
        requested_metrics=requested,
    )


def _metric_series_context(
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


def _build_input_frames(request: RollingStatelessInput) -> _RollingInputFrames:
    return _RollingInputFrames(
        portfolio=_build_returns_df(request.returns),
        benchmark=_build_returns_df(request.benchmark_returns),
        risk_free=_build_returns_df(request.risk_free_returns),
    )


def _response_metadata(
    request: RollingStatelessInput,
    *,
    requested_metrics: Sequence[str],
    calculation_supportability: RiskCalculationSupportability,
) -> RollingMetadata:
    options = request.rolling_options
    return RollingMetadata(
        request_fingerprint=fingerprint_model(request),
        annualization_basis=options.annualization_basis,
        requested_metrics=[str(metric) for metric in requested_metrics],
        window_lengths_requested=list(options.window_lengths),
        window_count_requested=len(options.window_lengths),
        alignment_policy=options.alignment_policy,
        min_observations_policy=options.min_observations_policy,
        include_time_series=options.include_time_series,
        benchmark_context=_request_dependency_context(
            requested_metrics,
            ROLLING_BENCHMARK_METRICS,
        ),
        risk_free_context=_request_dependency_context(
            requested_metrics,
            {ROLLING_SHARPE_METRIC},
        ),
        calculation_supportability=calculation_supportability,
    )


def _empty_response(
    request: RollingStatelessInput,
    *,
    input_mode: RollingInputMode,
) -> RollingResponse:
    calculation_supportability = supportability_from_period_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results={},
    )
    record_operation_supportability(
        operation="risk/rolling-metrics",
        supportability=calculation_supportability,
    )
    requested_metrics = [str(metric) for metric in request.rolling_options.metrics]
    return RollingResponse(
        input_mode=input_mode,
        scope=request.scope,
        results={},
        metadata=_response_metadata(
            request,
            requested_metrics=requested_metrics,
            calculation_supportability=calculation_supportability,
        ),
    )


def _period_series(
    *,
    frames: _RollingInputFrames,
    request: RollingStatelessInput,
    period: RiskRequestPeriod,
    open_date: date,
) -> _RollingPeriodSeries:
    start, end = risk_helpers._resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date,
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    portfolio_period_pp = _filter_period(frames.portfolio, start=start, end=end)
    benchmark_period = (
        _filter_period(frames.benchmark, start=start, end=end) / 100.0
        if not frames.benchmark.empty
        else pd.Series(dtype="float64")
    )
    risk_free_period = (
        _filter_period(frames.risk_free, start=start, end=end) / 100.0
        if not frames.risk_free.empty
        else pd.Series(dtype="float64")
    )
    return _RollingPeriodSeries(
        name=_period_name(period),
        start=start,
        end=end,
        portfolio_pp=portfolio_period_pp,
        portfolio_decimal=portfolio_period_pp / 100.0,
        benchmark_decimal=benchmark_period,
        risk_free_decimal=risk_free_period,
    )


def _insufficient_period_result(
    period_series: _RollingPeriodSeries,
    *,
    options: RollingOptions,
    requested_metrics: Sequence[str],
) -> RollingPeriodResult:
    return RollingPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        series_count=len(period_series.portfolio_pp),
        benchmark_series_count=0,
        aligned_benchmark_series_count=0,
        risk_free_series_count=0,
        aligned_risk_free_series_count=0,
        window_lengths_requested=list(options.window_lengths),
        window_count_requested=len(options.window_lengths),
        window_lengths_emitted=[],
        window_count_emitted=0,
        benchmark_context=_benchmark_context(requested_metrics, 0, 0),
        risk_free_context=_risk_free_context(requested_metrics, 0, 0),
        window_results=[],
        quality_flags=[],
        error="Insufficient data",
    )


def _metric_values_for_window(
    metric_name: str,
    period_series: _RollingPeriodSeries,
    *,
    window_length: int,
    options: RollingOptions,
    min_obs: int,
) -> tuple[pd.Series, list[str], int, int]:
    if metric_name == "ROLLING_VOLATILITY":
        return (
            _rolling_volatility(
                period_series.portfolio_decimal,
                window_length=window_length,
                annualization_basis=options.annualization_basis,
                min_obs=min_obs,
            ),
            [],
            0,
            0,
        )
    if metric_name == ROLLING_SHARPE_METRIC:
        metric_values, flags, aligned_count = _rolling_sharpe(
            period_series.portfolio_decimal,
            period_series.risk_free_decimal,
            window_length=window_length,
            annualization_basis=options.annualization_basis,
            min_obs=min_obs,
        )
        return metric_values, flags, 0, aligned_count
    if metric_name in ROLLING_BENCHMARK_METRICS:
        metric_values, flags, aligned_count = _rolling_benchmark_metrics(
            metric_name,
            period_series.portfolio_decimal,
            period_series.benchmark_decimal,
            window_length=window_length,
            annualization_basis=options.annualization_basis,
            min_obs=min_obs,
        )
        return metric_values, flags, aligned_count, 0
    if metric_name == ROLLING_MAX_DRAWDOWN_METRIC:
        return (
            _rolling_max_drawdown_metric(
                period_series.portfolio_decimal,
                window_length=window_length,
                min_obs=min_obs,
            ),
            [],
            0,
            0,
        )
    raise ValueError(f"Unsupported rolling metric: {metric_name}")


def _calculate_window_result(
    period_series: _RollingPeriodSeries,
    *,
    requested_metrics: Sequence[str],
    options: RollingOptions,
    window_length: int,
) -> _RollingWindowCalculation:
    min_obs = _min_observations(window_length, options.min_observations_policy)
    metric_series_map: dict[str, pd.Series] = {}
    quality_flags: set[str] = set()
    aligned_benchmark_series_count = 0
    aligned_risk_free_series_count = 0

    for metric_name in requested_metrics:
        metric_values, flags, benchmark_count, risk_free_count = _metric_values_for_window(
            metric_name,
            period_series,
            window_length=window_length,
            options=options,
            min_obs=min_obs,
        )
        metric_series_map[metric_name] = metric_values
        quality_flags.update(flags)
        aligned_benchmark_series_count = max(aligned_benchmark_series_count, benchmark_count)
        aligned_risk_free_series_count = max(aligned_risk_free_series_count, risk_free_count)

    summaries = {
        metric_name: _summary(series, min_obs=min_obs)
        for metric_name, series in metric_series_map.items()
    }
    metric_points = (
        _window_series_points(metric_series_map) if options.include_time_series else None
    )
    return _RollingWindowCalculation(
        window_result=RollingWindowResult(
            window_length=window_length,
            metric_summaries=summaries,
            metric_series=metric_points,
            metric_series_context=_metric_series_context(
                include_time_series=options.include_time_series,
                metric_points=metric_points,
            ),
        ),
        quality_flags=quality_flags,
        aligned_benchmark_series_count=aligned_benchmark_series_count,
        aligned_risk_free_series_count=aligned_risk_free_series_count,
    )


def _calculate_period_result(
    period_series: _RollingPeriodSeries,
    *,
    options: RollingOptions,
    requested_metrics: Sequence[str],
) -> RollingPeriodResult:
    if len(period_series.portfolio_pp) < 2:
        return _insufficient_period_result(
            period_series,
            options=options,
            requested_metrics=requested_metrics,
        )

    window_results: list[RollingWindowResult] = []
    period_flags: set[str] = set()
    aligned_benchmark_series_count = 0
    aligned_risk_free_series_count = 0

    for window_length in options.window_lengths:
        calculation = _calculate_window_result(
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

    return RollingPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        series_count=len(period_series.portfolio_decimal),
        benchmark_series_count=len(period_series.benchmark_decimal),
        aligned_benchmark_series_count=aligned_benchmark_series_count,
        risk_free_series_count=len(period_series.risk_free_decimal),
        aligned_risk_free_series_count=aligned_risk_free_series_count,
        window_lengths_requested=list(options.window_lengths),
        window_count_requested=len(options.window_lengths),
        window_lengths_emitted=[result.window_length for result in window_results],
        window_count_emitted=len(window_results),
        benchmark_context=_benchmark_context(
            requested_metrics,
            len(period_series.benchmark_decimal),
            aligned_benchmark_series_count,
        ),
        risk_free_context=_risk_free_context(
            requested_metrics,
            len(period_series.risk_free_decimal),
            aligned_risk_free_series_count,
        ),
        window_results=window_results,
        quality_flags=sorted(period_flags),
        error=None,
    )


def calculate_rolling_metrics(
    request: RollingStatelessInput,
    *,
    input_mode: RollingInputMode,
) -> RollingResponse:
    frames = _build_input_frames(request)
    if frames.portfolio.empty:
        return _empty_response(request, input_mode=input_mode)

    open_date = cast(pd.Timestamp, frames.portfolio.index.min()).date()
    options = request.rolling_options
    requested_metrics = [str(metric) for metric in options.metrics]

    results: dict[str, RollingPeriodResult] = {}
    for period in request.periods:
        period_series = _period_series(
            frames=frames,
            request=request,
            period=period,
            open_date=open_date,
        )
        results[period_series.name] = _calculate_period_result(
            period_series,
            options=options,
            requested_metrics=requested_metrics,
        )

    calculation_supportability = supportability_from_period_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results=results,
    )
    record_operation_supportability(
        operation="risk/rolling-metrics",
        supportability=calculation_supportability,
    )
    return RollingResponse(
        input_mode=input_mode,
        scope=request.scope,
        results=results,
        metadata=_response_metadata(
            request,
            requested_metrics=requested_metrics,
            calculation_supportability=calculation_supportability,
        ),
    )
