from __future__ import annotations

from typing import Sequence

from prometheus_client import Counter, Histogram

from app.contracts.risk import (
    RiskCalculationSupportability,
    RiskPeriodResult,
    RiskResponseMetadata,
    RiskResponse,
    RiskStatelessCalculationInput,
)
from app.services.calculation_supportability import record_operation_supportability
from app.services.risk import calculation_orchestrator as risk_orchestrator
from app.services.risk import helpers as risk_helpers

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

BENCHMARK_METRICS = risk_helpers.BENCHMARK_METRICS


def _record_metric_request(metrics: Sequence[str]) -> None:
    for metric in metrics:
        RISK_METRIC_REQUESTED_TOTAL.labels(metric_name=metric).inc()


def _build_metadata(
    request: RiskStatelessCalculationInput,
    *,
    annual_factor: int,
    periodic_rf: float,
    calculation_supportability: RiskCalculationSupportability,
) -> RiskResponseMetadata:
    return risk_orchestrator.build_request_metadata(
        request,
        annual_factor=annual_factor,
        periodic_rf=periodic_rf,
        calculation_supportability=calculation_supportability,
    )


def _resolve_calculation_supportability(
    request: RiskStatelessCalculationInput,
    results: dict[str, RiskPeriodResult],
) -> RiskCalculationSupportability:
    return risk_orchestrator.resolve_calculation_supportability(request, results)


def calculate_risk(request: RiskStatelessCalculationInput) -> RiskResponse:
    _record_metric_request(request.metrics)
    annual_factor = risk_orchestrator.derive_annualization_factor(request)

    returns_df, benchmark_df = risk_orchestrator.resolve_return_frames(request)
    if returns_df.empty:
        calculation_supportability = _resolve_calculation_supportability(request, {})
        record_operation_supportability(
            operation="risk/calculate",
            supportability=calculation_supportability,
        )
        return RiskResponse(
            scope=request.scope,
            results={},
            metadata=_build_metadata(
                request,
                annual_factor=annual_factor,
                periodic_rf=0.0,
                calculation_supportability=calculation_supportability,
            ),
        )

    periodic_rf, periodic_mar = risk_orchestrator.resolve_periodic_rates(
        request=request,
        annual_factor=annual_factor,
    )

    results = risk_orchestrator.build_period_results(
        request,
        annual_factor=annual_factor,
        periodic_rf=periodic_rf,
        periodic_mar=periodic_mar,
        returns_df=returns_df,
        benchmark_df=benchmark_df,
        duration_seconds=RISK_METRIC_DURATION_SECONDS,
    )

    calculation_supportability = _resolve_calculation_supportability(request, results)
    record_operation_supportability(
        operation="risk/calculate",
        supportability=calculation_supportability,
    )
    return RiskResponse(
        scope=request.scope,
        results=results,
        metadata=_build_metadata(
            request,
            annual_factor=annual_factor,
            periodic_rf=periodic_rf,
            calculation_supportability=calculation_supportability,
        ),
    )
