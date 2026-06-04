from __future__ import annotations

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
    RollingPeriodResult,
    RollingRequestDependencyContext,
    RollingRiskFreeContext,
    RollingResponse,
    RollingStatelessInput,
    RollingWindowResult,
)
from app.contracts.risk import ReturnPoint, RiskRequestPeriod
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_period_results,
)
from app.services.risk import helpers as risk_helpers


ROLLING_SHARPE_METRIC = "ROLLING_SHARPE"
ROLLING_MAX_DRAWDOWN_METRIC = "ROLLING_MAX_DRAWDOWN"


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


def calculate_rolling_metrics(
    request: RollingStatelessInput,
    *,
    input_mode: RollingInputMode,
) -> RollingResponse:
    portfolio_df = _build_returns_df(request.returns)
    benchmark_df = _build_returns_df(request.benchmark_returns)
    risk_free_df = _build_returns_df(request.risk_free_returns)

    if portfolio_df.empty:
        calculation_supportability = supportability_from_period_results(
            returns=request.returns,
            as_of_date=request.scope.as_of_date,
            results={},
        )
        record_operation_supportability(
            operation="risk/rolling-metrics",
            supportability=calculation_supportability,
        )
        return RollingResponse(
            input_mode=input_mode,
            scope=request.scope,
            results={},
            metadata=RollingMetadata(
                request_fingerprint=fingerprint_model(request),
                annualization_basis=request.rolling_options.annualization_basis,
                requested_metrics=[str(metric) for metric in request.rolling_options.metrics],
                window_lengths_requested=list(request.rolling_options.window_lengths),
                window_count_requested=len(request.rolling_options.window_lengths),
                alignment_policy=request.rolling_options.alignment_policy,
                min_observations_policy=request.rolling_options.min_observations_policy,
                include_time_series=request.rolling_options.include_time_series,
                benchmark_context=_request_dependency_context(
                    request.rolling_options.metrics,
                    ROLLING_BENCHMARK_METRICS,
                ),
                risk_free_context=_request_dependency_context(
                    request.rolling_options.metrics,
                    {ROLLING_SHARPE_METRIC},
                ),
                calculation_supportability=calculation_supportability,
            ),
        )

    open_date = cast(pd.Timestamp, portfolio_df.index.min()).date()
    options = request.rolling_options
    requested_metrics = [str(metric) for metric in options.metrics]

    results: dict[str, RollingPeriodResult] = {}
    for period in request.periods:
        start, end = risk_helpers._resolve_period(
            period.type,
            request.scope.as_of_date,
            open_date,
            year=period.year,
            from_date=period.from_date,
            to_date=period.to_date,
        )
        period_name = _period_name(period)

        portfolio_period_pp = _filter_period(portfolio_df, start=start, end=end)
        if len(portfolio_period_pp) < 2:
            results[period_name] = RollingPeriodResult(
                start_date=start,
                end_date=end,
                series_count=len(portfolio_period_pp),
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
            continue

        portfolio_period = portfolio_period_pp / 100.0
        benchmark_period = (
            _filter_period(benchmark_df, start=start, end=end) / 100.0
            if not benchmark_df.empty
            else pd.Series(dtype="float64")
        )
        risk_free_period = (
            _filter_period(risk_free_df, start=start, end=end) / 100.0
            if not risk_free_df.empty
            else pd.Series(dtype="float64")
        )

        window_results: list[RollingWindowResult] = []
        period_flags: set[str] = set()
        aligned_benchmark_series_count = 0
        aligned_risk_free_series_count = 0

        for window_length in options.window_lengths:
            min_obs = _min_observations(window_length, options.min_observations_policy)
            metric_series_map: dict[str, pd.Series] = {}

            for metric_name in requested_metrics:
                if metric_name == "ROLLING_VOLATILITY":
                    metric_series_map[metric_name] = _rolling_volatility(
                        portfolio_period,
                        window_length=window_length,
                        annualization_basis=options.annualization_basis,
                        min_obs=min_obs,
                    )
                elif metric_name == ROLLING_SHARPE_METRIC:
                    metric_values, flags, aligned_count = _rolling_sharpe(
                        portfolio_period,
                        risk_free_period,
                        window_length=window_length,
                        annualization_basis=options.annualization_basis,
                        min_obs=min_obs,
                    )
                    metric_series_map[metric_name] = metric_values
                    period_flags.update(flags)
                    aligned_risk_free_series_count = max(
                        aligned_risk_free_series_count,
                        aligned_count,
                    )
                elif metric_name in ROLLING_BENCHMARK_METRICS:
                    metric_values, flags, aligned_count = _rolling_benchmark_metrics(
                        metric_name,
                        portfolio_period,
                        benchmark_period,
                        window_length=window_length,
                        annualization_basis=options.annualization_basis,
                        min_obs=min_obs,
                    )
                    metric_series_map[metric_name] = metric_values
                    period_flags.update(flags)
                    aligned_benchmark_series_count = max(
                        aligned_benchmark_series_count,
                        aligned_count,
                    )
                elif metric_name == ROLLING_MAX_DRAWDOWN_METRIC:
                    metric_series_map[metric_name] = _rolling_max_drawdown_metric(
                        portfolio_period,
                        window_length=window_length,
                        min_obs=min_obs,
                    )
                else:
                    raise ValueError(f"Unsupported rolling metric: {metric_name}")

            summaries = {
                metric_name: _summary(series, min_obs=min_obs)
                for metric_name, series in metric_series_map.items()
            }

            metric_points = (
                _window_series_points(metric_series_map) if options.include_time_series else None
            )

            window_results.append(
                RollingWindowResult(
                    window_length=window_length,
                    metric_summaries=summaries,
                    metric_series=metric_points,
                    metric_series_context=_metric_series_context(
                        include_time_series=options.include_time_series,
                        metric_points=metric_points,
                    ),
                )
            )

        results[period_name] = RollingPeriodResult(
            start_date=start,
            end_date=end,
            series_count=len(portfolio_period),
            benchmark_series_count=len(benchmark_period),
            aligned_benchmark_series_count=aligned_benchmark_series_count,
            risk_free_series_count=len(risk_free_period),
            aligned_risk_free_series_count=aligned_risk_free_series_count,
            window_lengths_requested=list(options.window_lengths),
            window_count_requested=len(options.window_lengths),
            window_lengths_emitted=[result.window_length for result in window_results],
            window_count_emitted=len(window_results),
            benchmark_context=_benchmark_context(
                requested_metrics,
                len(benchmark_period),
                aligned_benchmark_series_count,
            ),
            risk_free_context=_risk_free_context(
                requested_metrics,
                len(risk_free_period),
                aligned_risk_free_series_count,
            ),
            window_results=window_results,
            quality_flags=sorted(period_flags),
            error=None,
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
        metadata=RollingMetadata(
            request_fingerprint=fingerprint_model(request),
            annualization_basis=options.annualization_basis,
            requested_metrics=requested_metrics,
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
        ),
    )
