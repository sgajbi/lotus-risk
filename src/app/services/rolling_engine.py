from __future__ import annotations

from datetime import date
from math import sqrt
from typing import cast

import numpy as np
import pandas as pd

from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingInputMode,
    RollingMetadata,
    RollingMetricSeriesPoint,
    RollingMetricSummary,
    RollingPeriodResult,
    RollingResponse,
    RollingStatelessInput,
    RollingWindowResult,
)
from app.contracts.risk import ReturnPoint, RiskRequestPeriod
from app.services.risk_engine import _resolve_period


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


def _summary(values: pd.Series) -> RollingMetricSummary:
    clean = values.dropna()
    if clean.empty:
        return RollingMetricSummary(
            latest=None,
            average=None,
            minimum=None,
            maximum=None,
            p05=None,
            p50=None,
            p95=None,
        )
    return RollingMetricSummary(
        latest=float(clean.iloc[-1]),
        average=float(clean.mean()),
        minimum=float(clean.min()),
        maximum=float(clean.max()),
        p05=float(clean.quantile(0.05)),
        p50=float(clean.quantile(0.50)),
        p95=float(clean.quantile(0.95)),
    )


def _rolling_volatility(series_decimal: pd.Series, *, window_length: int, annualization_basis: int, min_obs: int) -> pd.Series:
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
) -> tuple[pd.Series, list[str]]:
    aligned = pd.merge(
        portfolio_decimal.to_frame("portfolio"),
        risk_free_decimal.to_frame("risk_free"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    if aligned.empty:
        return pd.Series(dtype="float64"), ["metric:ROLLING_SHARPE:alignment_empty"]

    active = aligned["portfolio"] - aligned["risk_free"]
    roll_mean = active.rolling(window=window_length, min_periods=min_obs).mean()
    roll_std = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1)
    sharpe = (roll_mean / roll_std) * sqrt(annualization_basis)
    sharpe = sharpe.replace([np.inf, -np.inf], np.nan)
    flags: list[str] = []
    if roll_std.dropna().eq(0).any():
        flags.append("metric:ROLLING_SHARPE:zero_volatility_window")
    return sharpe, flags


def _rolling_benchmark_metrics(
    metric_name: str,
    portfolio_decimal: pd.Series,
    benchmark_decimal: pd.Series,
    *,
    window_length: int,
    annualization_basis: int,
    min_obs: int,
) -> tuple[pd.Series, list[str]]:
    aligned = pd.merge(
        portfolio_decimal.to_frame("portfolio"),
        benchmark_decimal.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    if aligned.empty:
        return pd.Series(dtype="float64"), [f"metric:{metric_name}:alignment_empty"]

    portfolio = aligned["portfolio"]
    benchmark = aligned["benchmark"]

    if metric_name == "ROLLING_TRACKING_ERROR":
        active = portfolio - benchmark
        result = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1) * sqrt(
            annualization_basis
        )
        return result, []

    if metric_name == "ROLLING_INFORMATION_RATIO":
        active = portfolio - benchmark
        roll_mean = active.rolling(window=window_length, min_periods=min_obs).mean()
        roll_std = active.rolling(window=window_length, min_periods=min_obs).std(ddof=1)
        result = (roll_mean / roll_std) * sqrt(annualization_basis)
        result = result.replace([np.inf, -np.inf], np.nan)
        flags: list[str] = []
        if roll_std.dropna().eq(0).any():
            flags.append("metric:ROLLING_INFORMATION_RATIO:zero_tracking_error_window")
        return result, flags

    if metric_name == "ROLLING_BETA":
        roll_cov = portfolio.rolling(window=window_length, min_periods=min_obs).cov(benchmark)
        roll_var = benchmark.rolling(window=window_length, min_periods=min_obs).var(ddof=1)
        result = roll_cov / roll_var
        result = result.replace([np.inf, -np.inf], np.nan)
        flags = []
        if roll_var.dropna().eq(0).any():
            flags.append("metric:ROLLING_BETA:benchmark_variance_zero")
        return result, flags

    raise ValueError(f"Unsupported rolling benchmark metric: {metric_name}")


def _rolling_max_drawdown_metric(series_decimal: pd.Series, *, window_length: int, min_obs: int) -> pd.Series:
    return series_decimal.rolling(window=window_length, min_periods=min_obs).apply(
        _rolling_max_drawdown,
        raw=True,
    )


def _window_series_points(metric_series_map: dict[str, pd.Series]) -> list[RollingMetricSeriesPoint]:
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


def calculate_rolling_metrics(
    request: RollingStatelessInput,
    *,
    input_mode: RollingInputMode,
) -> RollingResponse:
    portfolio_df = _build_returns_df(request.returns)
    benchmark_df = _build_returns_df(request.benchmark_returns)
    risk_free_df = _build_returns_df(request.risk_free_returns)

    if portfolio_df.empty:
        return RollingResponse(
            input_mode=input_mode,
            scope=request.scope,
            results={},
            metadata=RollingMetadata(
                annualization_basis=request.rolling_options.annualization_basis,
                alignment_policy=request.rolling_options.alignment_policy,
            ),
        )

    open_date = cast(pd.Timestamp, portfolio_df.index.min()).date()
    options = request.rolling_options
    requested_metrics = list(options.metrics)

    results: dict[str, RollingPeriodResult] = {}
    for period in request.periods:
        start, end = _resolve_period(
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
                    metric_values, flags = _rolling_sharpe(
                        portfolio_period,
                        risk_free_period,
                        window_length=window_length,
                        annualization_basis=options.annualization_basis,
                        min_obs=min_obs,
                    )
                    metric_series_map[metric_name] = metric_values
                    period_flags.update(flags)
                elif metric_name in ROLLING_BENCHMARK_METRICS:
                    metric_values, flags = _rolling_benchmark_metrics(
                        metric_name,
                        portfolio_period,
                        benchmark_period,
                        window_length=window_length,
                        annualization_basis=options.annualization_basis,
                        min_obs=min_obs,
                    )
                    metric_series_map[metric_name] = metric_values
                    period_flags.update(flags)
                elif metric_name == ROLLING_MAX_DRAWDOWN_METRIC:
                    metric_series_map[metric_name] = _rolling_max_drawdown_metric(
                        portfolio_period,
                        window_length=window_length,
                        min_obs=min_obs,
                    )
                else:
                    raise ValueError(f"Unsupported rolling metric: {metric_name}")

            summaries = {
                metric_name: _summary(series)
                for metric_name, series in metric_series_map.items()
            }

            metric_points = (
                _window_series_points(metric_series_map)
                if options.include_time_series
                else None
            )

            window_results.append(
                RollingWindowResult(
                    window_length=window_length,
                    metric_summaries=summaries,
                    metric_series=metric_points,
                )
            )

        results[period_name] = RollingPeriodResult(
            start_date=start,
            end_date=end,
            series_count=len(portfolio_period),
            window_results=window_results,
            quality_flags=sorted(period_flags),
            error=None,
        )

    return RollingResponse(
        input_mode=input_mode,
        scope=request.scope,
        results=results,
        metadata=RollingMetadata(
            annualization_basis=options.annualization_basis,
            alignment_policy=options.alignment_policy,
        ),
    )
