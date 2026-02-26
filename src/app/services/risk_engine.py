from __future__ import annotations

from datetime import date, timedelta
from typing import SupportsFloat, cast, Sequence
from math import sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd
from prometheus_client import Counter, Histogram

from app.contracts.risk import (
    RiskCalculationRequest,
    RiskPeriodResult,
    RiskResponse,
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
        }

    trough_idx = cast(pd.Timestamp, drawdown.idxmin())
    peak_idx = cast(pd.Timestamp, wealth.loc[:trough_idx].idxmax())
    max_drawdown = _as_number(cast(float, drawdown.loc[trough_idx] * 100))
    trough_date = str(trough_idx.date())
    return {
        "max_drawdown": max_drawdown,
        "peak_date": str(peak_idx.date()),
        "trough_date": trough_date,
        "max_drawdown_date": trough_date,
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


def _beta(portfolio: pd.Series, benchmark: pd.Series) -> float:
    covariance = np.cov(portfolio, benchmark, ddof=1)
    denominator = covariance[1, 1]
    if denominator == 0:
        raise ValueError("Benchmark variance is zero")
    return _as_number(covariance[0, 1] / denominator)


def _tracking_error(portfolio: pd.Series, benchmark: pd.Series, annual_factor: int) -> float:
    active = portfolio - benchmark
    return _as_number(active.std(ddof=1) * sqrt(annual_factor))


def _information_ratio(portfolio: pd.Series, benchmark: pd.Series, annual_factor: int) -> float:
    active = portfolio - benchmark
    tracking_err = active.std(ddof=1)
    if tracking_err == 0:
        raise ValueError("Tracking error is zero")
    return _as_number((active.mean() / tracking_err) * sqrt(annual_factor))


def _require_data(series: pd.Series, minimum: int = 2) -> None:
    if len(series.dropna()) < minimum:
        raise ValueError("Insufficient data")


def _metric_error(message: str) -> RiskValue:
    return RiskValue(value=None, details={"error": message})


def _record_metric_request(metrics: Sequence[str]) -> None:
    for metric in metrics:
        RISK_METRIC_REQUESTED_TOTAL.labels(metric_name=metric).inc()


def calculate_risk(request: RiskCalculationRequest) -> RiskResponse:
    _record_metric_request(request.metrics)

    returns_df = pd.DataFrame([{"date": p.date, "value": p.value} for p in request.returns])
    if returns_df.empty:
        return RiskResponse(scope=request.scope, results={})

    returns_df["date"] = pd.to_datetime(returns_df["date"])
    returns_df = returns_df.sort_values("date").set_index("date")

    benchmark_df = pd.DataFrame(
        [{"date": p.date, "value": p.value} for p in request.benchmark_returns]
    )
    if not benchmark_df.empty:
        benchmark_df["date"] = pd.to_datetime(benchmark_df["date"])
        benchmark_df = benchmark_df.sort_values("date").set_index("date")

    annual_factor = (
        request.options.annualization_factor
        or {
            "DAILY": 252,
            "WEEKLY": 52,
            "MONTHLY": 12,
        }[request.options.frequency]
    )

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
                    metric_map["VOLATILITY"] = RiskValue(
                        value=_as_number(metric_series.std(ddof=1) * sqrt(annual_factor))
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
                    if denominator == 0:
                        raise ValueError("Zero volatility")
                    sharpe = (
                        (metric_series.mean() / 100 - periodic_rf) / (denominator / 100)
                    ) * sqrt(annual_factor)
                    metric_map["SHARPE"] = RiskValue(value=_as_number(sharpe))
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
                    downside_deviation = _as_number(np.sqrt((downside**2).mean()))
                    if downside_deviation == 0:
                        raise ValueError("Zero downside deviation")
                    sortino = (
                        ((metric_series.mean() / 100) - periodic_mar) / downside_deviation
                    ) * sqrt(annual_factor)
                    metric_map["SORTINO"] = RiskValue(value=_as_number(sortino))
                except ValueError as exc:
                    metric_map["SORTINO"] = _metric_error(str(exc))

        benchmark_metrics = [m for m in request.metrics if m in BENCHMARK_METRICS]
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

                if "BETA" in benchmark_metrics:
                    with RISK_METRIC_DURATION_SECONDS.labels(metric_name="BETA").time():
                        try:
                            _require_data(portfolio_series)
                            metric_map["BETA"] = RiskValue(
                                value=_beta(portfolio_series, benchmark_series)
                            )
                        except ValueError as exc:
                            metric_map["BETA"] = _metric_error(str(exc))

                if "TRACKING_ERROR" in benchmark_metrics:
                    with RISK_METRIC_DURATION_SECONDS.labels(metric_name="TRACKING_ERROR").time():
                        try:
                            _require_data(portfolio_series)
                            metric_map["TRACKING_ERROR"] = RiskValue(
                                value=_tracking_error(
                                    portfolio_series, benchmark_series, annual_factor
                                )
                            )
                        except ValueError as exc:
                            metric_map["TRACKING_ERROR"] = _metric_error(str(exc))

                if "INFORMATION_RATIO" in benchmark_metrics:
                    with RISK_METRIC_DURATION_SECONDS.labels(
                        metric_name="INFORMATION_RATIO"
                    ).time():
                        try:
                            _require_data(portfolio_series)
                            metric_map["INFORMATION_RATIO"] = RiskValue(
                                value=_information_ratio(
                                    portfolio_series, benchmark_series, annual_factor
                                )
                            )
                        except ValueError as exc:
                            metric_map["INFORMATION_RATIO"] = _metric_error(str(exc))

        if "VAR" in request.metrics:
            with RISK_METRIC_DURATION_SECONDS.labels(metric_name="VAR").time():
                try:
                    _require_data(metric_series)
                    base_var = _calculate_var_by_method(
                        metric_series, request.options.var.method, request.options.var.confidence
                    )
                    scaled_var = base_var * sqrt(request.options.var.horizon_days)
                    details = None
                    if request.options.var.include_expected_shortfall:
                        base_es = _expected_shortfall(metric_series, base_var)
                        details = {
                            "expected_shortfall": base_es * sqrt(request.options.var.horizon_days)
                        }
                    metric_map["VAR"] = RiskValue(value=scaled_var, details=details)
                except ValueError as exc:
                    metric_map["VAR"] = _metric_error(str(exc))

        results[period_name] = RiskPeriodResult(startDate=start, endDate=end, metrics=metric_map)

    return RiskResponse(scope=request.scope, results=results)
