from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TypedDict, cast

import numpy as np
import pandas as pd

from app.contracts.attribution import (
    AttributionContributor,
    AttributionMetric,
    AttributionOptions,
    AttributionSetResult,
    AttributionType,
    ExposurePoint,
    HistoricalAttributionStatelessInput,
    GroupingDimension,
)
from app.contracts.risk import ReturnPoint


class DecompositionRow(TypedDict):
    group_key: str
    weight_average: float | None
    marginal_contribution: float | None
    component_contribution: float | None
    percent_contribution: float | None


@dataclass(frozen=True)
class AttributionCalculationInputs:
    metric_series: pd.Series
    group_matrix: pd.DataFrame
    risk_total: float


@dataclass(frozen=True)
class AttributionSourceFrames:
    returns_df: pd.DataFrame
    benchmark_df: pd.DataFrame
    exposure_df: pd.DataFrame
    benchmark_exposure_df: pd.DataFrame


@dataclass(frozen=True)
class AttributionPrecalculation:
    calculation_inputs: AttributionCalculationInputs | None
    early_result: AttributionSetResult | None


def _returns_df(points: list[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in points])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _exposure_df(points: list[ExposurePoint]) -> pd.DataFrame:
    columns = ["date", "grouping_dimension", "group_key", "group_label", "weight"]
    df = pd.DataFrame(
        [
            {
                "date": point.date,
                "grouping_dimension": point.grouping_dimension,
                "group_key": point.group_key,
                "group_label": point.group_label,
                "weight": point.weight,
            }
            for point in points
        ],
        columns=columns,
    )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def build_source_frames(request: HistoricalAttributionStatelessInput) -> AttributionSourceFrames:
    return AttributionSourceFrames(
        returns_df=_returns_df(request.returns),
        benchmark_df=_returns_df(request.benchmark_returns),
        exposure_df=_exposure_df(request.exposure_history),
        benchmark_exposure_df=_exposure_df(request.benchmark_exposure_history),
    )


def window_returns(series_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    return series_df.loc[(series_df.index >= start) & (series_df.index <= end), "value"]


def _pivot_exposure(
    df: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    grouping_dimension: GroupingDimension,
) -> tuple[pd.DataFrame, dict[str, str | None], list[str]]:
    scoped = df.loc[
        (df["date"] >= start)
        & (df["date"] <= end)
        & (df["grouping_dimension"] == grouping_dimension)
    ]
    if scoped.empty:
        return pd.DataFrame(), {}, [f"grouping:{grouping_dimension}:no_exposure_data"]

    labels_raw = scoped.groupby("group_key", as_index=True)["group_label"].last().to_dict()
    labels = {str(key): cast(str | None, value) for key, value in labels_raw.items()}
    weights = scoped.pivot_table(index="date", columns="group_key", values="weight", aggfunc="mean")
    weights = weights.sort_index().fillna(0.0)

    flags: list[str] = []
    sums = weights.sum(axis=1)
    if (sums - 1.0).abs().max() > 0.02:
        flags.append(f"grouping:{grouping_dimension}:weight_not_sum_to_one")
    return weights, labels, flags


def _component_decomposition(
    *,
    group_matrix: pd.DataFrame,
    metric_series: pd.Series,
    contribution_denominator: float,
    annualization_basis: int,
) -> list[DecompositionRow]:
    if group_matrix.empty or metric_series.empty:
        return []

    std = float(metric_series.std(ddof=1))
    if np.isclose(std, 0.0):
        return []

    metric_mean = group_matrix.mean(axis=0)
    decomposition: list[DecompositionRow] = []
    for group_key in group_matrix.columns:
        group_series = group_matrix[group_key]
        cov = float(np.cov(group_series, metric_series, ddof=1)[0, 1])
        component = float((cov / std) * sqrt(annualization_basis))
        marginal = (
            float(component / metric_mean[group_key])
            if not np.isclose(metric_mean[group_key], 0.0)
            else None
        )
        percent = (
            float(component / contribution_denominator)
            if not np.isclose(contribution_denominator, 0.0)
            else None
        )
        decomposition.append(
            {
                "group_key": str(group_key),
                "weight_average": float(metric_mean[group_key]),
                "marginal_contribution": marginal,
                "component_contribution": component,
                "percent_contribution": percent,
            }
        )
    return decomposition


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


def _total_risk_inputs(
    *,
    returns_series: pd.Series,
    exposure_weights: pd.DataFrame,
    annualization_basis: int,
) -> AttributionCalculationInputs:
    metric_series = returns_series
    aligned_weights = exposure_weights.reindex(index=metric_series.index, fill_value=0.0)
    return AttributionCalculationInputs(
        metric_series=metric_series,
        group_matrix=aligned_weights.mul(metric_series, axis=0),
        risk_total=float(metric_series.std(ddof=1) * sqrt(annualization_basis)),
    )


def _active_risk_inputs(
    *,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    exposure_weights: pd.DataFrame,
    benchmark_weights: pd.DataFrame,
    annualization_basis: int,
) -> AttributionCalculationInputs | None:
    aligned = pd.merge(
        returns_series.to_frame("portfolio"),
        benchmark_series.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    if aligned.empty:
        return None

    metric_series = aligned["portfolio"] - aligned["benchmark"]
    common_cols = sorted(set(exposure_weights.columns).union(set(benchmark_weights.columns)))
    p_w = exposure_weights.reindex(columns=common_cols, fill_value=0.0)
    b_w = benchmark_weights.reindex(columns=common_cols, fill_value=0.0)
    p_w = p_w.reindex(index=metric_series.index, fill_value=0.0)
    b_w = b_w.reindex(index=metric_series.index, fill_value=0.0)
    active_w = p_w - b_w
    return AttributionCalculationInputs(
        metric_series=metric_series,
        group_matrix=active_w.mul(metric_series, axis=0),
        risk_total=float(metric_series.std(ddof=1) * sqrt(annualization_basis)),
    )


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


def _attribution_calculation_inputs(
    *,
    attribution_type: AttributionType,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    exposure_weights: pd.DataFrame,
    benchmark_weights: pd.DataFrame,
    annualization_basis: int,
) -> AttributionCalculationInputs | None:
    if attribution_type == "TOTAL_RISK":
        return _total_risk_inputs(
            returns_series=returns_series,
            exposure_weights=exposure_weights,
            annualization_basis=annualization_basis,
        )
    return _active_risk_inputs(
        returns_series=returns_series,
        benchmark_series=benchmark_series,
        exposure_weights=exposure_weights,
        benchmark_weights=benchmark_weights,
        annualization_basis=annualization_basis,
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
    rows = _component_decomposition(
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

    calculation_inputs = _attribution_calculation_inputs(
        attribution_type=attribution_type,
        returns_series=returns_series,
        benchmark_series=benchmark_series,
        exposure_weights=exposure_weights,
        benchmark_weights=benchmark_weights,
        annualization_basis=annualization_basis,
    )
    precalculation = _attribution_set_precalculation_result(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        calculation_inputs=calculation_inputs,
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
        weights, labels, flags = _pivot_exposure(
            frames.exposure_df,
            start=start,
            end=end,
            grouping_dimension=grouping_dimension,
        )
        if benchmark_required:
            benchmark_weights, benchmark_labels, benchmark_flags = _pivot_exposure(
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
