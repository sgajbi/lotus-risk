from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

import numpy as np
import pandas as pd

from src.app.contracts.risk import (
    RiskCalculationRequest,
    RiskPeriodResult,
    RiskResponse,
    RiskValue,
)


@dataclass(frozen=True)
class ResolvedPeriod:
    name: str
    start: date
    end: date


def _resolve_period(period_type: str, as_of: date, open_date: date, *, year: int | None = None, from_date: date | None = None, to_date: date | None = None) -> tuple[date, date]:
    if period_type == "CUSTOM":
        if from_date is None or to_date is None:
            raise ValueError("CUSTOM period requires fromDate and toDate")
        return from_date, to_date
    if period_type == "YEAR":
        if year is None:
            raise ValueError("YEAR period requires year")
        return date(year, 1, 1), date(year, 12, 31)
    if period_type == "YTD":
        return date(as_of.year, 1, 1), as_of
    if period_type == "MTD":
        return date(as_of.year, as_of.month, 1), as_of
    if period_type == "QTD":
        quarter_start_month = ((as_of.month - 1) // 3) * 3 + 1
        return date(as_of.year, quarter_start_month, 1), as_of
    if period_type == "ONE_YEAR":
        return date(as_of.year - 1, as_of.month, as_of.day), as_of
    if period_type == "THREE_YEAR":
        return date(as_of.year - 3, as_of.month, as_of.day), as_of
    if period_type == "SI":
        return open_date, as_of
    raise ValueError(f"Unsupported period type: {period_type}")


def _resample_returns(returns: pd.Series, frequency: str) -> pd.Series:
    if returns.empty:
        return returns
    if frequency == "DAILY":
        return returns
    rule = {"WEEKLY": "W-FRI", "MONTHLY": "ME"}[frequency]
    return returns.resample(rule).apply(lambda x: ((1 + x / 100).prod() - 1) * 100).dropna()


def _to_log_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return returns
    return np.log1p(returns / 100) * 100


def _annual_to_periodic(rate: float, annual_factor: int) -> float:
    return (1 + rate) ** (1 / annual_factor) - 1


def _drawdown(returns: pd.Series) -> dict:
    wealth = (1 + returns / 100).cumprod()
    peak = wealth.cummax()
    dd = wealth / peak - 1
    min_dd = float(dd.min()) if not dd.empty else 0.0
    min_idx = dd.idxmin() if not dd.empty else None
    return {
        "max_drawdown": min_dd * 100,
        "max_drawdown_date": str(min_idx.date()) if min_idx is not None else None,
    }


def _var_historical(returns: pd.Series, confidence: float) -> float:
    alpha = 1.0 - confidence
    return float(np.percentile(returns, alpha * 100))


def _expected_shortfall(returns: pd.Series, var_value: float) -> float:
    tail = returns[returns <= var_value]
    if tail.empty:
        return float(var_value)
    return float(tail.mean())


def _beta(p: pd.Series, b: pd.Series) -> float:
    cov = np.cov(p, b, ddof=1)
    denom = cov[1, 1]
    if denom == 0:
        raise ValueError("Benchmark variance is zero")
    return float(cov[0, 1] / denom)


def _tracking_error(p: pd.Series, b: pd.Series, annual_factor: int) -> float:
    active = p - b
    return float(active.std(ddof=1) * sqrt(annual_factor))


def _information_ratio(p: pd.Series, b: pd.Series, annual_factor: int) -> float:
    active = p - b
    te = active.std(ddof=1)
    if te == 0:
        raise ValueError("Tracking error is zero")
    return float((active.mean() / te) * sqrt(annual_factor))


def _require_data(series: pd.Series, minimum: int = 2) -> None:
    if len(series.dropna()) < minimum:
        raise ValueError("Insufficient data")


def calculate_risk(request: RiskCalculationRequest) -> RiskResponse:
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

    annual_factor = request.options.annualization_factor or {
        "DAILY": 252,
        "WEEKLY": 52,
        "MONTHLY": 12,
    }[request.options.frequency]

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
            (returns_df.index >= pd.Timestamp(start)) & (returns_df.index <= pd.Timestamp(end)), "value"
        ]
        period_returns = _resample_returns(period_returns, request.options.frequency)

        for_drawdown = period_returns
        for_metrics = _to_log_returns(period_returns) if request.options.use_log_returns else period_returns

        metric_map: dict[str, RiskValue] = {}

        if "VOLATILITY" in request.metrics:
            try:
                _require_data(for_metrics)
                value = float(for_metrics.std(ddof=1) * sqrt(annual_factor))
                metric_map["VOLATILITY"] = RiskValue(value=value)
            except ValueError as exc:
                metric_map["VOLATILITY"] = RiskValue(value=None, details={"error": str(exc)})

        if "DRAWDOWN" in request.metrics:
            try:
                _require_data(for_drawdown)
                dd = _drawdown(for_drawdown)
                metric_map["DRAWDOWN"] = RiskValue(value=dd["max_drawdown"], details=dd)
            except ValueError as exc:
                metric_map["DRAWDOWN"] = RiskValue(value=None, details={"error": str(exc)})

        if "SHARPE" in request.metrics:
            try:
                _require_data(for_metrics)
                denom = for_metrics.std(ddof=1)
                if denom == 0:
                    raise ValueError("Zero volatility")
                sharpe = ((for_metrics.mean() / 100 - periodic_rf) / (denom / 100)) * sqrt(annual_factor)
                metric_map["SHARPE"] = RiskValue(value=float(sharpe))
            except ValueError as exc:
                metric_map["SHARPE"] = RiskValue(value=None, details={"error": str(exc)})

        if "SORTINO" in request.metrics:
            try:
                _require_data(for_metrics)
                downside = ((for_metrics / 100) - periodic_mar)
                downside = downside[downside < 0]
                if downside.empty:
                    raise ValueError("No downside observations")
                downside_dev = float(np.sqrt((downside**2).mean()))
                if downside_dev == 0:
                    raise ValueError("Zero downside deviation")
                sortino = (((for_metrics.mean() / 100) - periodic_mar) / downside_dev) * sqrt(annual_factor)
                metric_map["SORTINO"] = RiskValue(value=float(sortino))
            except ValueError as exc:
                metric_map["SORTINO"] = RiskValue(value=None, details={"error": str(exc)})

        need_bench = any(
            metric in request.metrics for metric in {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}
        )
        if need_bench and not benchmark_df.empty:
            bench_period = benchmark_df.loc[
                (benchmark_df.index >= pd.Timestamp(start)) & (benchmark_df.index <= pd.Timestamp(end)), "value"
            ]
            bench_period = _resample_returns(bench_period, request.options.frequency)
            if request.options.use_log_returns:
                bench_period = _to_log_returns(bench_period)
            aligned = pd.merge(
                for_metrics.to_frame("p"),
                bench_period.to_frame("b"),
                left_index=True,
                right_index=True,
                how="inner",
            )
            p = aligned["p"]
            b = aligned["b"]
            if "BETA" in request.metrics:
                try:
                    _require_data(p)
                    metric_map["BETA"] = RiskValue(value=_beta(p, b))
                except ValueError as exc:
                    metric_map["BETA"] = RiskValue(value=None, details={"error": str(exc)})
            if "TRACKING_ERROR" in request.metrics:
                try:
                    _require_data(p)
                    metric_map["TRACKING_ERROR"] = RiskValue(
                        value=_tracking_error(p, b, annual_factor)
                    )
                except ValueError as exc:
                    metric_map["TRACKING_ERROR"] = RiskValue(value=None, details={"error": str(exc)})
            if "INFORMATION_RATIO" in request.metrics:
                try:
                    _require_data(p)
                    metric_map["INFORMATION_RATIO"] = RiskValue(
                        value=_information_ratio(p, b, annual_factor)
                    )
                except ValueError as exc:
                    metric_map["INFORMATION_RATIO"] = RiskValue(
                        value=None, details={"error": str(exc)}
                    )

        if "VAR" in request.metrics:
            try:
                _require_data(for_metrics)
                base_var = _var_historical(for_metrics, request.options.var.confidence)
                scaled_var = base_var * sqrt(request.options.var.horizon_days)
                details = None
                if request.options.var.include_expected_shortfall:
                    base_es = _expected_shortfall(for_metrics, base_var)
                    details = {"expected_shortfall": base_es * sqrt(request.options.var.horizon_days)}
                metric_map["VAR"] = RiskValue(value=scaled_var, details=details)
            except ValueError as exc:
                metric_map["VAR"] = RiskValue(value=None, details={"error": str(exc)})

        results[period_name] = RiskPeriodResult(startDate=start, endDate=end, metrics=metric_map)

    return RiskResponse(scope=request.scope, results=results)
