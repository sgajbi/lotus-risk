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
from app.services.risk.period_resolution import resolve_period


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
    start_date, end_date = resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date.date(),
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    return start_date, end_date, pd.Timestamp(start_date), pd.Timestamp(end_date)


def _period_returns_series(
    *,
    frames: AttributionSourceFrames,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    return window_returns(frames.returns_df, start, end) / 100.0


def _period_benchmark_series(
    *,
    frames: AttributionSourceFrames,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    if frames.benchmark_df.empty:
        return pd.Series(dtype="float64")
    return window_returns(frames.benchmark_df, start, end) / 100.0


def _insufficient_attribution_result(
    *,
    start_date: dt.date,
    end_date: dt.date,
) -> HistoricalAttributionPeriodResult:
    return HistoricalAttributionPeriodResult(
        start_date=start_date,
        end_date=end_date,
        attribution_sets=[],
        error="Insufficient data",
    )


def _attribution_period_result(
    *,
    start_date: dt.date,
    end_date: dt.date,
    options: AttributionOptions,
    frames: AttributionSourceFrames,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> HistoricalAttributionPeriodResult:
    return HistoricalAttributionPeriodResult(
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
    returns_series = _period_returns_series(frames=frames, start=start, end=end)
    benchmark_series = _period_benchmark_series(
        frames=frames,
        start=start,
        end=end,
    )
    if len(returns_series.dropna()) < 2:
        return name, _insufficient_attribution_result(start_date=start_date, end_date=end_date)

    return name, _attribution_period_result(
        start_date=start_date,
        end_date=end_date,
        options=options,
        frames=frames,
        returns_series=returns_series,
        benchmark_series=benchmark_series,
        start=start,
        end=end,
    )


def _historical_attribution_period_results(
    *,
    request: HistoricalAttributionStatelessInput,
    frames: AttributionSourceFrames,
    options: AttributionOptions,
) -> dict[str, HistoricalAttributionPeriodResult]:
    open_timestamp = cast(pd.Timestamp, frames.returns_df.index.min())
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
    return results


def calculate_historical_attribution(
    request: HistoricalAttributionStatelessInput,
    *,
    input_mode: AttributionInputMode,
) -> HistoricalAttributionResponse:
    frames = build_source_frames(request)
    if frames.returns_df.empty:
        return _empty_attribution_response(request=request, input_mode=input_mode)

    options = request.attribution_options
    results = _historical_attribution_period_results(
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
