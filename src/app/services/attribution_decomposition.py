from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.contracts.attribution import (
    AttributionContributor,
    AttributionMetric,
    AttributionOptions,
    AttributionSetResult,
    AttributionType,
    GroupingDimension,
)
from app.services.attribution_calculation import (
    AttributionCalculationInputs,
    DecompositionRow,
    attribution_calculation_inputs,
    component_decomposition,
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


def _empty_attribution_set(
    *,
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    quality_flags: list[str],
) -> AttributionSetResult:
    return AttributionSetResult(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        total_value=None,
        reconciled_sum=None,
        residual=None,
        contributors=[],
        quality_flags=quality_flags,
    )


def _unsupported_metric_set(
    *,
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    base_flags: list[str],
) -> AttributionSetResult | None:
    if attribution_type == "TOTAL_RISK" and metric != "VOLATILITY":
        return _empty_attribution_set(
            attribution_type=attribution_type,
            metric=metric,
            grouping_dimension=grouping_dimension,
            quality_flags=base_flags + [f"metric:{metric}:unsupported_for_total_risk"],
        )
    if attribution_type == "ACTIVE_RISK" and metric != "TRACKING_ERROR":
        return _empty_attribution_set(
            attribution_type=attribution_type,
            metric=metric,
            grouping_dimension=grouping_dimension,
            quality_flags=base_flags + [f"metric:{metric}:unsupported_for_active_risk"],
        )
    return None


def _attribution_contributors(
    *,
    rows: list[DecompositionRow],
    group_labels: dict[str, str | None],
) -> list[AttributionContributor]:
    return [
        AttributionContributor(
            group_key=row["group_key"],
            group_label=group_labels.get(row["group_key"]),
            weight_average=row["weight_average"],
            marginal_contribution=row["marginal_contribution"],
            component_contribution=row["component_contribution"],
            percent_contribution=row["percent_contribution"],
        )
        for row in rows
    ]


def _reconciled_attribution_set(
    *,
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    risk_total: float,
    contributors: list[AttributionContributor],
    quality_flags: list[str],
) -> AttributionSetResult:
    reconciled_sum = float(sum(c.component_contribution or 0.0 for c in contributors))
    residual = float(risk_total - reconciled_sum)
    return AttributionSetResult(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        total_value=risk_total,
        reconciled_sum=reconciled_sum,
        residual=residual,
        contributors=contributors,
        quality_flags=quality_flags,
    )


def _calculated_attribution_set(
    *,
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    calculation_inputs: AttributionCalculationInputs,
    group_labels: dict[str, str | None],
    annualization_basis: int,
    quality_flags: list[str],
) -> AttributionSetResult:
    rows = component_decomposition(
        group_matrix=calculation_inputs.group_matrix,
        metric_series=calculation_inputs.metric_series,
        contribution_denominator=calculation_inputs.risk_total,
        annualization_basis=annualization_basis,
    )
    return _reconciled_attribution_set(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        risk_total=calculation_inputs.risk_total,
        contributors=_attribution_contributors(rows=rows, group_labels=group_labels),
        quality_flags=quality_flags,
    )


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
            early_result=_empty_attribution_set(
                attribution_type=attribution_type,
                metric=metric,
                grouping_dimension=grouping_dimension,
                quality_flags=quality_flags + ["active_risk:alignment_empty"],
            ),
        )

    if len(calculation_inputs.metric_series.dropna()) < 2:
        return AttributionPrecalculation(
            calculation_inputs=None,
            early_result=_empty_attribution_set(
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
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    exposure_weights: pd.DataFrame,
    benchmark_weights: pd.DataFrame,
    annualization_basis: int,
    quality_flags: list[str],
) -> AttributionPrecalculation:
    calculation_inputs = attribution_calculation_inputs(
        attribution_type=attribution_type,
        returns_series=returns_series,
        benchmark_series=benchmark_series,
        exposure_weights=exposure_weights,
        benchmark_weights=benchmark_weights,
        annualization_basis=annualization_basis,
    )
    return _attribution_set_precalculation_result(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        calculation_inputs=calculation_inputs,
        quality_flags=quality_flags,
    )


def build_attribution_set(
    *,
    attribution_type: AttributionType,
    metric: AttributionMetric,
    grouping_dimension: GroupingDimension,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    exposure_weights: pd.DataFrame,
    benchmark_weights: pd.DataFrame,
    group_labels: dict[str, str | None],
    annualization_basis: int,
    base_flags: list[str],
) -> AttributionSetResult:
    flags = list(base_flags)

    unsupported = _unsupported_metric_set(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        base_flags=flags,
    )
    if unsupported is not None:
        return unsupported

    precalculation = _attribution_calculation_precalculation(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        returns_series=returns_series,
        benchmark_series=benchmark_series,
        exposure_weights=exposure_weights,
        benchmark_weights=benchmark_weights,
        annualization_basis=annualization_basis,
        quality_flags=flags,
    )
    if precalculation.early_result is not None:
        return precalculation.early_result
    if precalculation.calculation_inputs is None:
        raise RuntimeError("attribution precalculation returned no calculation inputs")

    return _calculated_attribution_set(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        calculation_inputs=precalculation.calculation_inputs,
        group_labels=group_labels,
        annualization_basis=annualization_basis,
        quality_flags=flags,
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
