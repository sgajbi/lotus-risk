from __future__ import annotations

import datetime as dt
from typing import cast

import pandas as pd

from app.contracts.attribution import (
    AttributionInputMode,
    AttributionOptions,
    HistoricalAttributionMetadata,
    HistoricalAttributionPeriodResult,
    HistoricalAttributionResponse,
    HistoricalAttributionStatelessInput,
)
from app.contracts.risk import RiskCalculationSupportability, RiskRequestPeriod
from app.services.attribution_decomposition import (
    AttributionSourceFrames,
    build_source_frames,
    window_returns,
)
from app.services.attribution_period_sets import build_period_attribution_sets
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_attribution_results,
    supportability_from_period_results,
)
from app.services.risk import helpers as risk_helpers


def _period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


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


def _resolved_period_window(
    *,
    period: RiskRequestPeriod,
    request: HistoricalAttributionStatelessInput,
    open_date: pd.Timestamp,
) -> tuple[dt.date, dt.date, pd.Timestamp, pd.Timestamp]:
    start_date, end_date = risk_helpers._resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date.date(),
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    return start_date, end_date, pd.Timestamp(start_date), pd.Timestamp(end_date)


def _calculate_period_attribution(
    *,
    period: RiskRequestPeriod,
    request: HistoricalAttributionStatelessInput,
    frames: AttributionSourceFrames,
    open_timestamp: pd.Timestamp,
    options: AttributionOptions,
) -> tuple[str, HistoricalAttributionPeriodResult]:
    start_date, end_date, start, end = _resolved_period_window(
        period=period,
        request=request,
        open_date=open_timestamp,
    )
    name = _period_name(period)
    returns_series = window_returns(frames.returns_df, start, end) / 100.0
    benchmark_series = (
        window_returns(frames.benchmark_df, start, end) / 100.0
        if not frames.benchmark_df.empty
        else pd.Series(dtype="float64")
    )
    if len(returns_series.dropna()) < 2:
        return name, HistoricalAttributionPeriodResult(
            start_date=start_date,
            end_date=end_date,
            attribution_sets=[],
            error="Insufficient data",
        )

    return name, HistoricalAttributionPeriodResult(
        start_date=start_date,
        end_date=end_date,
        attribution_sets=build_period_attribution_sets(
            options=options,
            frames=frames,
            returns_series=returns_series,
            benchmark_series=benchmark_series,
            start=start,
            end=end,
        ),
        error=None,
    )


def calculate_historical_attribution(
    request: HistoricalAttributionStatelessInput,
    *,
    input_mode: AttributionInputMode,
) -> HistoricalAttributionResponse:
    frames = build_source_frames(request)
    if frames.returns_df.empty:
        return _empty_attribution_response(request=request, input_mode=input_mode)

    open_timestamp = cast(pd.Timestamp, frames.returns_df.index.min())
    options = request.attribution_options

    results: dict[str, HistoricalAttributionPeriodResult] = {}
    for period in request.periods:
        name, period_result = _calculate_period_attribution(
            period=period,
            request=request,
            frames=frames,
            open_timestamp=open_timestamp,
            options=options,
        )
        results[name] = period_result

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
