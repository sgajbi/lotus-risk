from __future__ import annotations

import pandas as pd
from prometheus_client import Histogram

from app.contracts.risk import (
    BenchmarkRequestContext,
    RiskCalculationRequest,
    RiskCalculationSupportability,
    RiskFreeContext,
    RiskPeriodResult,
    RiskResponseMetadata,
    RiskStatelessCalculationInput,
    RiskValue,
)
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import supportability_from_risk_metric_results
from app.services.risk import helpers as risk_helpers
from app.services.risk.period_metrics import BenchmarkContextPayload, calculate_period_metrics
from app.services.risk.period_windows import RiskPeriodWindow, risk_period_window

BENCHMARK_METRICS = risk_helpers.BENCHMARK_METRICS
RISK_FREE_METRICS = risk_helpers.RISK_METRICS_REQUIRING_RISK_FREE


def derive_annualization_factor(request: RiskStatelessCalculationInput) -> int:
    return (
        request.options.annualization_factor
        or {
            "DAILY": 252,
            "WEEKLY": 52,
            "MONTHLY": 12,
        }[request.options.frequency]
    )


def resolve_periodic_rates(
    *,
    request: RiskStatelessCalculationInput,
    annual_factor: int,
) -> tuple[float, float]:
    periodic_rf = 0.0
    if (
        request.options.risk_free_mode == "ANNUAL_RATE"
        and request.options.risk_free_annual_rate is not None
    ):
        periodic_rf = risk_helpers._annual_to_periodic(
            request.options.risk_free_annual_rate,
            annual_factor,
        )
    periodic_mar = risk_helpers._annual_to_periodic(request.options.mar_annual_rate, annual_factor)
    return periodic_rf, periodic_mar


def build_request_metadata(
    request: RiskStatelessCalculationInput,
    *,
    annual_factor: int,
    periodic_rf: float,
    calculation_supportability: RiskCalculationSupportability,
) -> RiskResponseMetadata:
    risk_free_requested = any(metric in RISK_FREE_METRICS for metric in request.metrics)
    benchmark_metrics = [str(metric) for metric in request.metrics if metric in BENCHMARK_METRICS]
    return RiskResponseMetadata(
        request_fingerprint=fingerprint_model(request),
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
        calculation_supportability=calculation_supportability,
        mar_annual_rate=request.options.mar_annual_rate,
        var_method=request.options.var.method,
        var_confidence=request.options.var.confidence,
        var_horizon_days=request.options.var.horizon_days,
    )


def resolve_calculation_supportability(
    request: RiskCalculationRequest,
    results: dict[str, RiskPeriodResult],
) -> RiskCalculationSupportability:
    return supportability_from_risk_metric_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results=results,
    )


def resolve_return_frames(
    request: RiskStatelessCalculationInput,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    returns_df = pd.DataFrame([{"date": p.date, "value": p.value} for p in request.returns])
    if not returns_df.empty:
        returns_df["date"] = pd.to_datetime(returns_df["date"])
        returns_df = returns_df.sort_values("date").set_index("date")

    benchmark_df = pd.DataFrame(
        [{"date": p.date, "value": p.value} for p in request.benchmark_returns]
    )
    if not benchmark_df.empty:
        benchmark_df["date"] = pd.to_datetime(benchmark_df["date"])
        benchmark_df = benchmark_df.sort_values("date").set_index("date")

    return returns_df, benchmark_df


def _period_result(
    *,
    period_window: RiskPeriodWindow,
    metric_map: dict[str, RiskValue],
    benchmark_context: BenchmarkContextPayload | None,
    aligned_count: int,
    benchmark_observation_count: int,
    benchmark_df: pd.DataFrame,
) -> RiskPeriodResult:
    return RiskPeriodResult(
        start_date=period_window.start.date(),
        end_date=period_window.end.date(),
        portfolio_observation_count=len(period_window.returns),
        benchmark_observation_count=(
            benchmark_observation_count
            if (not benchmark_df.empty and benchmark_context is not None)
            else 0
        ),
        aligned_benchmark_observation_count=(aligned_count if benchmark_context else 0),
        benchmark_context=benchmark_context,
        metrics=metric_map,
    )


def build_period_results(
    request: RiskStatelessCalculationInput,
    *,
    annual_factor: int,
    periodic_rf: float,
    periodic_mar: float,
    returns_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    duration_seconds: Histogram,
) -> dict[str, RiskPeriodResult]:
    benchmark_metrics_for_request = [
        metric for metric in request.metrics if metric in BENCHMARK_METRICS
    ]

    results: dict[str, RiskPeriodResult] = {}
    for period_index, _period in enumerate(request.periods):
        period_window = risk_period_window(
            request=request,
            period_index=period_index,
            returns_df=returns_df,
        )
        metric_map, benchmark_context, aligned_count, benchmark_observation_count = (
            calculate_period_metrics(
                request,
                start=period_window.start,
                end=period_window.end,
                annual_factor=annual_factor,
                periodic_rf=periodic_rf,
                periodic_mar=periodic_mar,
                period_returns=period_window.returns,
                benchmark_df=benchmark_df,
                benchmark_metrics=benchmark_metrics_for_request,
                duration_seconds=duration_seconds,
            )
        )

        results[period_window.name] = _period_result(
            period_window=period_window,
            metric_map=metric_map,
            benchmark_context=benchmark_context,
            aligned_count=aligned_count,
            benchmark_observation_count=benchmark_observation_count,
            benchmark_df=benchmark_df,
        )

    return results
