from __future__ import annotations

from app.contracts.risk import (
    RiskCalculationSupportability,
    RiskPeriodResult,
    RiskResponse,
    RiskResponseMetadata,
    RiskStatelessCalculationInput,
)
from app.services.calculation_supportability import record_operation_supportability
from app.services.observability_ports import (
    observe_risk_metric_duration,
    record_risk_metric_requests,
)
from app.services.risk import calculation_orchestrator as risk_orchestrator
from app.services.risk import helpers as risk_helpers

BENCHMARK_METRICS = risk_helpers.BENCHMARK_METRICS


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


def _risk_response(
    request: RiskStatelessCalculationInput,
    *,
    annual_factor: int,
    periodic_rf: float,
    results: dict[str, RiskPeriodResult],
) -> RiskResponse:
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


def calculate_risk(request: RiskStatelessCalculationInput) -> RiskResponse:
    record_risk_metric_requests(request.metrics)
    annual_factor = risk_orchestrator.derive_annualization_factor(request)

    returns_df, benchmark_df = risk_orchestrator.resolve_return_frames(request)
    if returns_df.empty:
        return _risk_response(
            request,
            annual_factor=annual_factor,
            periodic_rf=0.0,
            results={},
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
        observe_metric_duration=observe_risk_metric_duration,
    )

    return _risk_response(
        request,
        annual_factor=annual_factor,
        periodic_rf=periodic_rf,
        results=results,
    )
