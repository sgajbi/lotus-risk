from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.contracts.attribution import (
    AttributionOptions,
    AttributionSetResult,
    GroupingDimension,
)
from app.services.attribution_decomposition import AttributionSetBuildRequest, build_attribution_set
from app.services.attribution_source_frames import AttributionSourceFrames, pivot_exposure


def requires_benchmark_attribution(options: AttributionOptions) -> bool:
    return "ACTIVE_RISK" in options.attribution_types or "TRACKING_ERROR" in options.metrics


@dataclass(frozen=True)
class _PeriodExposureInputs:
    weights: pd.DataFrame
    benchmark_weights: pd.DataFrame
    labels: dict[str, str | None]
    flags: list[str]


def _period_exposure_inputs(
    *,
    frames: AttributionSourceFrames,
    grouping_dimension: GroupingDimension,
    start: pd.Timestamp,
    end: pd.Timestamp,
    benchmark_required: bool,
) -> _PeriodExposureInputs:
    weights, labels, flags = pivot_exposure(
        frames.exposure_df,
        start=start,
        end=end,
        grouping_dimension=grouping_dimension,
    )
    if not benchmark_required:
        return _PeriodExposureInputs(
            weights=weights,
            benchmark_weights=pd.DataFrame(),
            labels=labels,
            flags=flags,
        )

    benchmark_weights, benchmark_labels, benchmark_flags = pivot_exposure(
        frames.benchmark_exposure_df,
        start=start,
        end=end,
        grouping_dimension=grouping_dimension,
    )
    return _PeriodExposureInputs(
        weights=weights,
        benchmark_weights=benchmark_weights,
        labels={**labels, **benchmark_labels},
        flags=[*flags, *benchmark_flags],
    )


def _grouping_attribution_sets(
    *,
    options: AttributionOptions,
    grouping_dimension: GroupingDimension,
    exposure_inputs: _PeriodExposureInputs,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
) -> list[AttributionSetResult]:
    attribution_sets: list[AttributionSetResult] = []
    for attribution_type in options.attribution_types:
        for metric in options.metrics:
            attribution_sets.append(
                build_attribution_set(
                    AttributionSetBuildRequest(
                        attribution_type=attribution_type,
                        metric=metric,
                        grouping_dimension=grouping_dimension,
                        returns_series=returns_series,
                        benchmark_series=benchmark_series,
                        exposure_weights=exposure_inputs.weights,
                        benchmark_weights=exposure_inputs.benchmark_weights,
                        group_labels=exposure_inputs.labels,
                        annualization_basis=options.annualization_basis,
                        quality_flags=list(exposure_inputs.flags),
                    )
                )
            )
    return attribution_sets


def build_period_attribution_sets(
    *,
    options: AttributionOptions,
    frames: AttributionSourceFrames,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[AttributionSetResult]:
    period_sets: list[AttributionSetResult] = []
    benchmark_required = requires_benchmark_attribution(options)

    for grouping_dimension in options.grouping_dimensions:
        exposure_inputs = _period_exposure_inputs(
            frames=frames,
            grouping_dimension=grouping_dimension,
            start=start,
            end=end,
            benchmark_required=benchmark_required,
        )
        period_sets.extend(
            _grouping_attribution_sets(
                options=options,
                grouping_dimension=grouping_dimension,
                exposure_inputs=exposure_inputs,
                returns_series=returns_series,
                benchmark_series=benchmark_series,
            )
        )
    return period_sets


__all__ = ["build_period_attribution_sets", "requires_benchmark_attribution"]
