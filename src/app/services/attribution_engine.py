from __future__ import annotations

from app.contracts.attribution import (
    ATTRIBUTION_METRIC_UNIT_SEMANTICS,
    AttributionInputMode,
    AttributionOptions,
    HistoricalAttributionMetadata,
    HistoricalAttributionResponse,
    HistoricalAttributionStatelessInput,
)
from app.contracts.risk import RiskCalculationSupportability
from app.services.attribution_decomposition import build_source_frames
from app.services.attribution_period_results import (
    historical_attribution_period_results,
)
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_attribution_results,
    supportability_from_period_results,
)


def _historical_attribution_metadata(
    *,
    request: HistoricalAttributionStatelessInput,
    options: AttributionOptions,
    calculation_supportability: RiskCalculationSupportability,
) -> HistoricalAttributionMetadata:
    return HistoricalAttributionMetadata(
        request_fingerprint=fingerprint_model(request),
        covariance_method=options.covariance_method,
        annualization_basis=options.annualization_basis,
        metric_unit_semantics={
            str(metric): ATTRIBUTION_METRIC_UNIT_SEMANTICS[str(metric)]
            for metric in options.metrics
        },
        requested_attribution_types=list(options.attribution_types),
        requested_metrics=list(options.metrics),
        requested_grouping_dimensions=list(options.grouping_dimensions),
        min_observations_policy=options.min_observations_policy,
        calculation_supportability=calculation_supportability,
    )


def _empty_attribution_response(
    *,
    request: HistoricalAttributionStatelessInput,
    input_mode: AttributionInputMode,
) -> HistoricalAttributionResponse:
    calculation_supportability = supportability_from_period_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results={},
    )
    record_operation_supportability(
        operation="risk/historical-attribution",
        supportability=calculation_supportability,
    )
    return HistoricalAttributionResponse(
        input_mode=input_mode,
        scope=request.scope,
        results={},
        metadata=_historical_attribution_metadata(
            request=request,
            options=request.attribution_options,
            calculation_supportability=calculation_supportability,
        ),
    )


def calculate_historical_attribution(
    request: HistoricalAttributionStatelessInput,
    *,
    input_mode: AttributionInputMode,
) -> HistoricalAttributionResponse:
    frames = build_source_frames(request)
    if frames.returns_df.empty:
        return _empty_attribution_response(request=request, input_mode=input_mode)

    options = request.attribution_options
    results = historical_attribution_period_results(
        request=request,
        frames=frames,
        options=options,
    )
    calculation_supportability = supportability_from_attribution_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results=results,
    )
    record_operation_supportability(
        operation="risk/historical-attribution",
        supportability=calculation_supportability,
    )
    return HistoricalAttributionResponse(
        input_mode=input_mode,
        scope=request.scope,
        results=results,
        metadata=_historical_attribution_metadata(
            request=request,
            options=options,
            calculation_supportability=calculation_supportability,
        ),
    )
