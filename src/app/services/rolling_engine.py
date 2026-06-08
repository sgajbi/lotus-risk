from __future__ import annotations

from collections.abc import Sequence

from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingInputMode,
    RollingMetadata,
    RollingRequestDependencyContext,
    RollingResponse,
    RollingStatelessInput,
)
from app.contracts.risk import RiskCalculationSupportability
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_period_results,
)
from app.services.rolling_metric_series import ROLLING_SHARPE_METRIC
from app.services.rolling_period_results import rolling_period_results
from app.services.rolling_period_series import build_rolling_input_frames


def _request_dependency_context(
    requested_metrics: Sequence[str], dependency_metrics: set[str]
) -> RollingRequestDependencyContext:
    requested = [metric for metric in requested_metrics if metric in dependency_metrics]
    return RollingRequestDependencyContext(
        requested=bool(requested),
        requested_metrics=requested,
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


def calculate_rolling_metrics(
    request: RollingStatelessInput,
    *,
    input_mode: RollingInputMode,
) -> RollingResponse:
    frames = build_rolling_input_frames(request)
    if frames.portfolio.empty:
        return _empty_response(request, input_mode=input_mode)

    options = request.rolling_options
    requested_metrics = [str(metric) for metric in options.metrics]
    results = rolling_period_results(
        request,
        frames=frames,
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
