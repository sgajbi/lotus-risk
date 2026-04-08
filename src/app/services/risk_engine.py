from __future__ import annotations

from datetime import date, timedelta
from typing import SupportsFloat, cast, Sequence
from math import sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd
from prometheus_client import Counter, Histogram

from app.contracts.risk import (
    BenchmarkRequestContext,
    RiskFreeContext,
    RiskPeriodResult,
    RiskResponseMetadata,
    RiskResponse,
    RiskStatelessCalculationInput,
    RiskValue,
)

RISK_METRIC_REQUESTED_TOTAL = Counter(
    "risk_metric_requested_total",
    "Number of risk metric requests by metric name.",
    ["metric_name"],
)
RISK_METRIC_DURATION_SECONDS = Histogram(
    "risk_metric_duration_seconds",
    "Risk metric calculation duration by metric name.",
    ["metric_name"],
)

BENCHMARK_METRICS = {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}


def _as_number(number: SupportsFloat) -> float:
    return float(number)


def _resolve_period(
    period_type: str,
    as_of: date,
    open_date: date,
    *,
    year: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    if period_type == "EXPLICIT":
        if from_date is None or to_date is None:
            raise ValueError("EXPLICIT period requires from/to dates")
        start, end = from_date, to_date
    elif period_type == "YEAR":
        if year is None:
            raise ValueError("YEAR period requires year")
        start, end = date(year, 1, 1), date(year, 12, 31)
    elif period_type == "YTD":
        start, end = date(as_of.year, 1, 1), as_of
    elif period_type == "QTD":
        quarter_start_month = (as_of.month - 1) // 3 * 3 + 1
        start, end = date(as_of.year, quarter_start_month, 1), as_of
    elif period_type == "MTD":
        start, end = date(as_of.year, as_of.month, 1), as_of
    elif period_type == "ONE_YEAR":
        start, end = as_of - timedelta(days=365) + timedelta(days=1), as_of
    elif period_type == "THREE_YEAR":
        start, end = as_of - timedelta(days=365 * 3) + timedelta(days=1), as_of
    elif period_type == "FIVE_YEAR":
        start, end = as_of - timedelta(days=365 * 5) + timedelta(days=1), as_of
    elif period_type == "SI":
        start, end = open_date, as_of
    else:
        raise ValueError(f"Unsupported period type: {period_type}")

    return max(start, open_date), end


def _resample_returns(returns: pd.Series, frequency: str) -> pd.Series:
    if returns.empty:
        return returns
    if frequency == "DAILY":
        return returns
    rule = {"WEEKLY": "W-FRI", "MONTHLY": "ME"}[frequency]
    resampled = returns.resample(rule).apply(lambda x: ((1 + x / 100).prod() - 1) * 100).dropna()
    return cast(pd.Series, resampled)


def _to_log_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return returns
    return cast(pd.Series, np.log1p(returns / 100) * 100)


def _annual_to_periodic(rate: float, annual_factor: int) -> float:
    return float((1.0 + float(rate)) ** (1.0 / float(annual_factor)) - 1.0)


def _drawdown(returns: pd.Series) -> dict[str, str | float | None]:
    wealth = (1 + returns / 100).cumprod()
    peak = wealth.cummax()
    drawdown = wealth / peak - 1
    if drawdown.empty:
        return {
            "max_drawdown": 0.0,
            "peak_date": None,
            "trough_date": None,
            "max_drawdown_date": None,
            "recovery_date": None,
            "is_recovered": True,
            "days_to_trough": None,
            "days_to_recovery": None,
            "time_under_water_days": 0,
        }

    trough_idx = cast(pd.Timestamp, drawdown.idxmin())
    peak_idx = cast(pd.Timestamp, wealth.loc[:trough_idx].idxmax())
    max_drawdown = _as_number(cast(float, drawdown.loc[trough_idx] * 100))
    peak_value = _as_number(cast(float, peak.loc[trough_idx]))
    post_trough_wealth = wealth.loc[trough_idx:]
    recovery_candidates = post_trough_wealth[post_trough_wealth >= peak_value]
    recovery_idx = (
        cast(pd.Timestamp, recovery_candidates.index[0]) if not recovery_candidates.empty else None
    )
    days_to_trough = int((trough_idx - peak_idx).days)
    if recovery_idx is not None:
        days_to_recovery = int((recovery_idx - trough_idx).days)
        time_under_water_days = int((recovery_idx - peak_idx).days)
        recovery_date = str(recovery_idx.date())
    else:
        days_to_recovery = None
        time_under_water_days = int((wealth.index[-1] - peak_idx).days)
        recovery_date = None
    trough_date = str(trough_idx.date())
    return {
        "max_drawdown": max_drawdown,
        "peak_date": str(peak_idx.date()),
        "trough_date": trough_date,
        "max_drawdown_date": trough_date,
        "recovery_date": recovery_date,
        "is_recovered": recovery_idx is not None,
        "days_to_trough": days_to_trough,
        "days_to_recovery": days_to_recovery,
        "time_under_water_days": time_under_water_days,
    }


def _var_historical(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    return cast(float, np.percentile(returns, alpha * 100))


def _var_gaussian(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    z_score = NormalDist().inv_cdf(alpha)
    return _as_number(returns.mean() + returns.std(ddof=1) * z_score)


def _var_cornish_fisher(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    z_score = NormalDist().inv_cdf(alpha)
    skew = _as_number(cast(float, returns.skew()))
    kurt = _as_number(cast(float, returns.kurt()))
    z_cf = z_score
    z_cf += ((z_score**2) - 1) * skew / 6
    z_cf += ((z_score**3) - 3 * z_score) * kurt / 24
    z_cf -= ((2 * z_score**3) - 5 * z_score) * (skew**2) / 36
    return _as_number(returns.mean() + returns.std(ddof=1) * z_cf)


def _calculate_var_by_method(returns: pd.Series, method: str, confidence: float) -> float:
    if method == "HISTORICAL":
        return _var_historical(returns, confidence)
    if method == "GAUSSIAN":
        return _var_gaussian(returns, confidence)
    if method == "CORNISH_FISHER":
        return _var_cornish_fisher(returns, confidence)
    raise ValueError(f"Unsupported VaR method: {method}")


def _expected_shortfall(returns: pd.Series, var_value: float) -> float:
    tail = returns[returns <= var_value]
    if tail.empty:
        return _as_number(var_value)
    return _as_number(tail.mean())


def _beta(portfolio: pd.Series, benchmark: pd.Series) -> tuple[float, dict[str, float | int]]:
    covariance = np.cov(portfolio, benchmark, ddof=1)
    denominator = covariance[1, 1]
    if np.isclose(denominator, 0.0):
        raise ValueError("Benchmark variance is zero")
    covariance_pb = _as_number(covariance[0, 1])
    benchmark_variance = _as_number(denominator)
    return (
        _as_number(covariance_pb / benchmark_variance),
        {
            "aligned_observation_count": int(portfolio.count()),
            "portfolio_mean_return": _as_number(portfolio.mean() / 100),
            "benchmark_mean_return": _as_number(benchmark.mean() / 100),
            "covariance": covariance_pb,
            "benchmark_variance": benchmark_variance,
        },
    )


def _tracking_error(
    portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, dict[str, float | int]]:
    active = portfolio - benchmark
    active_std = _as_number(active.std(ddof=1))
    annualized_tracking_error = _as_number(active_std * sqrt(annual_factor))
    return (
        annualized_tracking_error,
        {
            "aligned_observation_count": int(active.count()),
            "annualization_factor": annual_factor,
            "portfolio_mean_return": _as_number(portfolio.mean() / 100),
            "benchmark_mean_return": _as_number(benchmark.mean() / 100),
            "active_mean_return": _as_number(active.mean() / 100),
            "active_volatility": active_std / 100,
            "annualized_tracking_error": annualized_tracking_error / 100,
        },
    )


def _information_ratio(
    portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, dict[str, float | int]]:
    active = portfolio - benchmark
    tracking_err = active.std(ddof=1)
    if np.isclose(tracking_err, 0.0):
        raise ValueError("Tracking error is zero")
    active_mean = _as_number(active.mean() / 100)
    tracking_error = _as_number(tracking_err / 100)
    annualized_active_return = _as_number(active_mean * annual_factor)
    annualized_tracking_error = _as_number(tracking_error * sqrt(annual_factor))
    return (
        _as_number((active.mean() / tracking_err) * sqrt(annual_factor)),
        {
            "aligned_observation_count": int(active.count()),
            "annualization_factor": annual_factor,
            "portfolio_mean_return": _as_number(portfolio.mean() / 100),
            "benchmark_mean_return": _as_number(benchmark.mean() / 100),
            "active_mean_return": active_mean,
            "tracking_error": tracking_error,
            "annualized_active_return": annualized_active_return,
            "annualized_tracking_error": annualized_tracking_error,
        },
    )


def _calculate_benchmark_metric(
    metric_name: str, portfolio: pd.Series, benchmark: pd.Series, annual_factor: int
) -> tuple[float, dict[str, float | int]]:
    if metric_name == "BETA":
        return _beta(portfolio, benchmark)
    if metric_name == "TRACKING_ERROR":
        return _tracking_error(portfolio, benchmark, annual_factor)
    if metric_name == "INFORMATION_RATIO":
        return _information_ratio(portfolio, benchmark, annual_factor)
    raise ValueError(f"Unsupported benchmark metric: {metric_name}")


def _require_data(series: pd.Series, minimum: int = 2) -> None:
    if len(series.dropna()) < minimum:
        raise ValueError("Insufficient data")


def _metric_error(message: str) -> RiskValue:
    return RiskValue(value=None, details={"error": message})


def _record_metric_request(metrics: Sequence[str]) -> None:
    for metric in metrics:
        RISK_METRIC_REQUESTED_TOTAL.labels(metric_name=metric).inc()


def _build_metadata(
    request: RiskStatelessCalculationInput,
    *,
    annual_factor: int,
    periodic_rf: float,
) -> RiskResponseMetadata:
    risk_free_requested = "SHARPE" in request.metrics
    benchmark_metrics = [metric for metric in request.metrics if metric in BENCHMARK_METRICS]
    return RiskResponseMetadata(
        frequency=request.options.frequency,
        annualization_factor=annual_factor,
        use_log_returns=request.options.use_log_returns,
        risk_free_mode=request.options.risk_free_mode,
        risk_free_annual_rate=request.options.risk_free_annual_rate,
        risk_free_context=RiskFreeContext(
            requested=risk_free_requested,
            applied=risk_free_requested,
            reason=(
                "NOT_REQUESTED"
                if not risk_free_requested
                else (
                    "ANNUAL_RATE_APPLIED"
                    if request.options.risk_free_mode == "ANNUAL_RATE"
                    and request.options.risk_free_annual_rate is not None
                    else "ZERO_RATE"
                )
            ),
            periodic_rate=periodic_rf if risk_free_requested else 0.0,
        ),
        benchmark_context=BenchmarkRequestContext(
            requested=bool(benchmark_metrics),
            requested_metrics=benchmark_metrics,
        ),
        mar_annual_rate=request.options.mar_annual_rate,
        var_method=request.options.var.method,
        var_confidence=request.options.var.confidence,
        var_horizon_days=request.options.var.horizon_days,
    )


def calculate_risk(request: RiskStatelessCalculationInput) -> RiskResponse:
    _record_metric_request(request.metrics)

    annual_factor = (
        request.options.annualization_factor
        or {
            "DAILY": 252,
            "WEEKLY": 52,
            "MONTHLY": 12,
        }[request.options.frequency]
    )

    returns_df = pd.DataFrame([{"date": p.date, "value": p.value} for p in request.returns])
    if returns_df.empty:
        return RiskResponse(
            scope=request.scope,
            results={},
            metadata=_build_metadata(request, annual_factor=annual_factor, periodic_rf=0.0),
        )

    returns_df["date"] = pd.to_datetime(returns_df["date"])
    returns_df = returns_df.sort_values("date").set_index("date")

    benchmark_df = pd.DataFrame(
        [{"date": p.date, "value": p.value} for p in request.benchmark_returns]
    )
    if not benchmark_df.empty:
        benchmark_df["date"] = pd.to_datetime(benchmark_df["date"])
        benchmark_df = benchmark_df.sort_values("date").set_index("date")

    periodic_rf = 0.0
    if (
        request.options.risk_free_mode == "ANNUAL_RATE"
        and request.options.risk_free_annual_rate is not None
    ):
        periodic_rf = _annual_to_periodic(request.options.risk_free_annual_rate, annual_factor)
    periodic_mar = _annual_to_periodic(request.options.mar_annual_rate, annual_factor)

    results: dict[str, RiskPeriodResult] = {}
    for period in request.periods:
        start, end = _resolve_period(
            period.type,
            request.scope.as_of_date,
            request.portfolio_open_date,
            year=period.year,
            from_date=period.from_date,
            to_date=period.to_date,
        )
        period_name = period.name or period.type

        period_returns = returns_df.loc[
            (returns_df.index >= pd.Timestamp(start)) & (returns_df.index <= pd.Timestamp(end)),
            "value",
        ]
        period_returns = _resample_returns(period_returns, request.options.frequency)
        drawdown_series = period_returns
        metric_series = (
            _to_log_returns(period_returns) if request.options.use_log_returns else period_returns
        )

        metric_map: dict[str, RiskValue] = {}

        if "VOLATILITY" in request.metrics:
            with RISK_METRIC_DURATION_SECONDS.labels(metric_name="VOLATILITY").time():
                try:
                    _require_data(metric_series)
                    standard_deviation = _as_number(metric_series.std(ddof=1) / 100)
                    metric_map["VOLATILITY"] = RiskValue(
                        value=_as_number(standard_deviation * sqrt(annual_factor) * 100),
                        details={
                            "observation_count": int(metric_series.count()),
                            "standard_deviation": standard_deviation,
                            "annualization_factor": annual_factor,
                        },
                    )
                except ValueError as exc:
                    metric_map["VOLATILITY"] = _metric_error(str(exc))

        if "DRAWDOWN" in request.metrics:
            with RISK_METRIC_DURATION_SECONDS.labels(metric_name="DRAWDOWN").time():
                try:
                    _require_data(drawdown_series)
                    drawdown_data = _drawdown(drawdown_series)
                    drawdown_value = drawdown_data.get("max_drawdown")
                    metric_map["DRAWDOWN"] = RiskValue(
                        value=(
                            _as_number(drawdown_value)
                            if drawdown_value is not None and not isinstance(drawdown_value, str)
                            else None
                        ),
                        details=drawdown_data,
                    )
                except ValueError as exc:
                    metric_map["DRAWDOWN"] = _metric_error(str(exc))

        if "SHARPE" in request.metrics:
            with RISK_METRIC_DURATION_SECONDS.labels(metric_name="SHARPE").time():
                try:
                    _require_data(metric_series)
                    denominator = metric_series.std(ddof=1)
                    if np.isclose(denominator, 0.0):
                        raise ValueError("Zero volatility")
                    mean_return = _as_number(metric_series.mean() / 100)
                    excess_return = _as_number(mean_return - periodic_rf)
                    sharpe = (excess_return / (denominator / 100)) * sqrt(annual_factor)
                    metric_map["SHARPE"] = RiskValue(
                        value=_as_number(sharpe),
                        details={
                            "observation_count": int(metric_series.count()),
                            "annualization_factor": annual_factor,
                            "mean_return": mean_return,
                            "periodic_risk_free_rate": periodic_rf,
                            "excess_return": excess_return,
                            "annualized_excess_return": _as_number(excess_return * annual_factor),
                            "volatility": _as_number(denominator / 100),
                        },
                    )
                except ValueError as exc:
                    metric_map["SHARPE"] = _metric_error(str(exc))

        if "SORTINO" in request.metrics:
            with RISK_METRIC_DURATION_SECONDS.labels(metric_name="SORTINO").time():
                try:
                    _require_data(metric_series)
                    downside = (metric_series / 100) - periodic_mar
                    downside = downside[downside < 0]
                    if downside.empty:
                        raise ValueError("No downside observations")
                    downside_count = int(downside.count())
                    downside_deviation = _as_number(np.sqrt((downside**2).mean()))
                    mean_return = _as_number(metric_series.mean() / 100)
                    excess_return = _as_number(mean_return - periodic_mar)
                    sortino = (excess_return / downside_deviation) * sqrt(annual_factor)
                    metric_map["SORTINO"] = RiskValue(
                        value=_as_number(sortino),
                        details={
                            "observation_count": int(metric_series.count()),
                            "annualization_factor": annual_factor,
                            "mar_annual_rate": request.options.mar_annual_rate,
                            "periodic_mar": periodic_mar,
                            "mean_return": mean_return,
                            "excess_return": excess_return,
                            "annualized_excess_return": _as_number(excess_return * annual_factor),
                            "downside_observation_count": downside_count,
                            "downside_deviation": downside_deviation,
                        },
                    )
                except ValueError as exc:
                    metric_map["SORTINO"] = _metric_error(str(exc))

        benchmark_metrics = [m for m in request.metrics if m in BENCHMARK_METRICS]
        benchmark_period = pd.Series(dtype=float)
        aligned = pd.DataFrame(columns=["portfolio", "benchmark"])
        if benchmark_metrics:
            if benchmark_df.empty:
                for metric_name in benchmark_metrics:
                    metric_map[metric_name] = _metric_error(
                        "Benchmark returns required for benchmark-dependent metric"
                    )
            else:
                benchmark_period = benchmark_df.loc[
                    (benchmark_df.index >= pd.Timestamp(start))
                    & (benchmark_df.index <= pd.Timestamp(end)),
                    "value",
                ]
                benchmark_period = _resample_returns(benchmark_period, request.options.frequency)
                if request.options.use_log_returns:
                    benchmark_period = _to_log_returns(benchmark_period)

                aligned = pd.merge(
                    metric_series.to_frame("portfolio"),
                    benchmark_period.to_frame("benchmark"),
                    left_index=True,
                    right_index=True,
                    how="inner",
                )
                portfolio_series = aligned["portfolio"]
                benchmark_series = aligned["benchmark"]

                for metric_name in benchmark_metrics:
                    with RISK_METRIC_DURATION_SECONDS.labels(metric_name=metric_name).time():
                        try:
                            _require_data(portfolio_series)
                            value, details = _calculate_benchmark_metric(
                                metric_name, portfolio_series, benchmark_series, annual_factor
                            )
                            metric_map[metric_name] = RiskValue(
                                value=value,
                                details=details,
                            )
                        except ValueError as exc:
                            metric_map[metric_name] = _metric_error(str(exc))

        if "VAR" in request.metrics:
            with RISK_METRIC_DURATION_SECONDS.labels(metric_name="VAR").time():
                try:
                    _require_data(metric_series)
                    base_var = _calculate_var_by_method(
                        metric_series, request.options.var.method, request.options.var.confidence
                    )
                    horizon_scale_factor = _as_number(sqrt(request.options.var.horizon_days))
                    scaled_var = _as_number(base_var * horizon_scale_factor)
                    tail_observation_count = int((metric_series <= base_var).sum())
                    details: dict[str, str | float | int | bool | None] = {
                        "method": request.options.var.method,
                        "confidence": request.options.var.confidence,
                        "tail_probability": _as_number(1.0 - request.options.var.confidence),
                        "base_horizon_days": 1,
                        "horizon_days": request.options.var.horizon_days,
                        "horizon_scale_method": "SQRT_TIME",
                        "horizon_scale_factor": horizon_scale_factor,
                        "include_expected_shortfall": request.options.var.include_expected_shortfall,
                        "base_var": base_var,
                        "observation_count": int(metric_series.count()),
                        "tail_observation_count": tail_observation_count,
                    }
                    if request.options.var.include_expected_shortfall:
                        base_es = _expected_shortfall(metric_series, base_var)
                        details["base_expected_shortfall"] = base_es
                        details["expected_shortfall_observation_count"] = tail_observation_count
                        details["expected_shortfall"] = _as_number(base_es * horizon_scale_factor)
                    metric_map["VAR"] = RiskValue(value=scaled_var, details=details)
                except ValueError as exc:
                    metric_map["VAR"] = _metric_error(str(exc))

        benchmark_context: dict[str, str | bool | int | list[str]] | None = None
        if benchmark_metrics:
            requested = True
            available = not benchmark_df.empty
            aligned_count = len(aligned)
            benchmark_context = {
                "requested": requested,
                "available": available,
                "aligned": aligned_count > 0,
                "reason": (
                    "BENCHMARK_UNAVAILABLE"
                    if not available
                    else ("NO_ALIGNED_OBSERVATIONS" if aligned_count == 0 else "APPLIED")
                ),
                "requested_metric_count": len(benchmark_metrics),
                "requested_metrics": benchmark_metrics,
            }

        results[period_name] = RiskPeriodResult(
            start_date=start,
            end_date=end,
            portfolio_observation_count=len(period_returns),
            benchmark_observation_count=(len(benchmark_period) if benchmark_metrics else 0),
            aligned_benchmark_observation_count=(len(aligned) if benchmark_metrics else 0),
            benchmark_context=benchmark_context,
            metrics=metric_map,
        )

    return RiskResponse(
        scope=request.scope,
        results=results,
        metadata=_build_metadata(request, annual_factor=annual_factor, periodic_rf=periodic_rf),
    )
