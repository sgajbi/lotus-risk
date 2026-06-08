from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.contracts.attribution import (
    AttributionMetric,
    AttributionOptions,
    AttributionSetResult,
    AttributionType,
    GroupingDimension,
)
from app.services.attribution_calculation import (
    AttributionCalculationInputs,
    attribution_calculation_inputs,
)
from app.services.attribution_set_results import (
    calculated_attribution_set,
    empty_attribution_set,
)
from app.services.attribution_source_frames import (
    AttributionSourceFrames,
    build_source_frames,
    window_returns,
)


__all__ = [
    "AttributionSourceFrames",
    "build_period_attribution_sets",
    "build_source_frames",
    "requires_benchmark_attribution",
    "window_returns",
]


@dataclass(frozen=True)
class AttributionPrecalculation:
    calculation_inputs: AttributionCalculationInputs | None
    early_result: AttributionSetResult | None


@dataclass(frozen=True)
class AttributionSetBuildRequest:
    attribution_type: AttributionType
    metric: AttributionMetric
    grouping_dimension: GroupingDimension
    returns_series: pd.Series
    benchmark_series: pd.Series
    exposure_weights: pd.DataFrame
    benchmark_weights: pd.DataFrame
    group_labels: dict[str, str | None]
    annualization_basis: int
    quality_flags: list[str]


def _unsupported_metric_set(
    *,
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    base_flags: list[str],
) -> AttributionSetResult | None:
    if attribution_type == "TOTAL_RISK" and metric != "VOLATILITY":
        return empty_attribution_set(
            attribution_type=attribution_type,
            metric=metric,
            grouping_dimension=grouping_dimension,
            quality_flags=base_flags + [f"metric:{metric}:unsupported_for_total_risk"],
        )
    if attribution_type == "ACTIVE_RISK" and metric != "TRACKING_ERROR":
        return empty_attribution_set(
            attribution_type=attribution_type,
            metric=metric,
            grouping_dimension=grouping_dimension,
            quality_flags=base_flags + [f"metric:{metric}:unsupported_for_active_risk"],
        )
    return None


def _attribution_set_precalculation_result(
    *,
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    calculation_inputs: AttributionCalculationInputs | None,
    quality_flags: list[str],
) -> AttributionPrecalculation:
    if calculation_inputs is None:
        return AttributionPrecalculation(
            calculation_inputs=None,
            early_result=empty_attribution_set(
                attribution_type=attribution_type,
                metric=metric,
                grouping_dimension=grouping_dimension,
                quality_flags=quality_flags + ["active_risk:alignment_empty"],
            ),
        )

    if len(calculation_inputs.metric_series.dropna()) < 2:
        return AttributionPrecalculation(
            calculation_inputs=None,
            early_result=empty_attribution_set(
                attribution_type=attribution_type,
                metric=metric,
                grouping_dimension=grouping_dimension,
                quality_flags=quality_flags + ["series:insufficient_observations"],
            ),
        )
    return AttributionPrecalculation(
        calculation_inputs=calculation_inputs,
        early_result=None,
    )


def _attribution_calculation_precalculation(
    *,
    request: AttributionSetBuildRequest,
) -> AttributionPrecalculation:
    calculation_inputs = attribution_calculation_inputs(
        attribution_type=request.attribution_type,
        returns_series=request.returns_series,
        benchmark_series=request.benchmark_series,
        exposure_weights=request.exposure_weights,
        benchmark_weights=request.benchmark_weights,
        annualization_basis=request.annualization_basis,
    )
    return _attribution_set_precalculation_result(
        attribution_type=request.attribution_type,
        metric=request.metric,
        grouping_dimension=request.grouping_dimension,
        calculation_inputs=calculation_inputs,
        quality_flags=request.quality_flags,
    )


def _resolve_attribution_precalculation(
    request: AttributionSetBuildRequest,
) -> AttributionPrecalculation:
    unsupported = _unsupported_metric_set(
        attribution_type=request.attribution_type,
        metric=request.metric,
        grouping_dimension=request.grouping_dimension,
        base_flags=request.quality_flags,
    )
    if unsupported is not None:
        return AttributionPrecalculation(calculation_inputs=None, early_result=unsupported)
    return _attribution_calculation_precalculation(request=request)


def build_attribution_set(request: AttributionSetBuildRequest) -> AttributionSetResult:
    precalculation = _resolve_attribution_precalculation(request)
    if precalculation.early_result is not None:
        return precalculation.early_result
    if precalculation.calculation_inputs is None:
        raise RuntimeError("attribution precalculation returned no calculation inputs")

    return calculated_attribution_set(
        attribution_type=request.attribution_type,
        metric=request.metric,
        grouping_dimension=request.grouping_dimension,
        calculation_inputs=precalculation.calculation_inputs,
        group_labels=request.group_labels,
        annualization_basis=request.annualization_basis,
        quality_flags=request.quality_flags,
    )


def requires_benchmark_attribution(options: AttributionOptions) -> bool:
    from app.services.attribution_period_sets import requires_benchmark_attribution as _requires

    return _requires(options)


def build_period_attribution_sets(
    *,
    options: AttributionOptions,
    frames: AttributionSourceFrames,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[AttributionSetResult]:
    from app.services.attribution_period_sets import build_period_attribution_sets as _build

    return _build(
        options=options,
        frames=frames,
        returns_series=returns_series,
        benchmark_series=benchmark_series,
        start=start,
        end=end,
    )
