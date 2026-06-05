from __future__ import annotations

import pandas as pd

from app.contracts.attribution import (
    AttributionOptions,
    AttributionSetResult,
)
from app.services.attribution_decomposition import build_attribution_set
from app.services.attribution_source_frames import AttributionSourceFrames, pivot_exposure


def requires_benchmark_attribution(options: AttributionOptions) -> bool:
    return "ACTIVE_RISK" in options.attribution_types or "TRACKING_ERROR" in options.metrics


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
        weights, labels, flags = pivot_exposure(
            frames.exposure_df,
            start=start,
            end=end,
            grouping_dimension=grouping_dimension,
        )
        if benchmark_required:
            benchmark_weights, benchmark_labels, benchmark_flags = pivot_exposure(
                frames.benchmark_exposure_df,
                start=start,
                end=end,
                grouping_dimension=grouping_dimension,
            )
            labels = {**labels, **benchmark_labels}
            flags = [*flags, *benchmark_flags]
        else:
            benchmark_weights = pd.DataFrame()

        for attribution_type in options.attribution_types:
            for metric in options.metrics:
                period_sets.append(
                    build_attribution_set(
                        attribution_type=attribution_type,
                        metric=metric,
                        grouping_dimension=grouping_dimension,
                        returns_series=returns_series,
                        benchmark_series=benchmark_series,
                        exposure_weights=weights,
                        benchmark_weights=benchmark_weights,
                        group_labels=labels,
                        annualization_basis=options.annualization_basis,
                        base_flags=flags,
                    )
                )
    return period_sets


__all__ = ["build_period_attribution_sets", "requires_benchmark_attribution"]
