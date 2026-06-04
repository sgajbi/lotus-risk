from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from math import sqrt
from typing import TypedDict, cast

import numpy as np
import pandas as pd

from app.contracts.attribution import (
    AttributionContributor,
    AttributionInputMode,
    AttributionMetric,
    AttributionOptions,
    AttributionSetResult,
    AttributionType,
    ExposurePoint,
    HistoricalAttributionMetadata,
    HistoricalAttributionPeriodResult,
    HistoricalAttributionResponse,
    HistoricalAttributionStatelessInput,
    GroupingDimension,
)
from app.contracts.risk import ReturnPoint, RiskCalculationSupportability, RiskRequestPeriod
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_attribution_results,
    supportability_from_period_results,
)
from app.services.risk import helpers as risk_helpers


class DecompositionRow(TypedDict):
    group_key: str
    weight_average: float | None
    marginal_contribution: float | None
    component_contribution: float | None
    percent_contribution: float | None


@dataclass(frozen=True)
class _AttributionCalculationInputs:
    metric_series: pd.Series
    group_matrix: pd.DataFrame
    risk_total: float


@dataclass(frozen=True)
class _AttributionSourceFrames:
    returns_df: pd.DataFrame
    benchmark_df: pd.DataFrame
    exposure_df: pd.DataFrame
    benchmark_exposure_df: pd.DataFrame


def _period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


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


def _window_returns(series_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
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
    total_value: float,
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
        percent = float(component / total_value) if not np.isclose(total_value, 0.0) else None
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
) -> _AttributionCalculationInputs:
    metric_series = returns_series
    aligned_weights = exposure_weights.reindex(index=metric_series.index, fill_value=0.0)
    return _AttributionCalculationInputs(
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
) -> _AttributionCalculationInputs | None:
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
    return _AttributionCalculationInputs(
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


def _build_attribution_set(
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

    if attribution_type == "TOTAL_RISK":
        calculation_inputs = _total_risk_inputs(
            returns_series=returns_series,
            exposure_weights=exposure_weights,
            annualization_basis=annualization_basis,
        )
    else:
        active_inputs = _active_risk_inputs(
            returns_series=returns_series,
            benchmark_series=benchmark_series,
            exposure_weights=exposure_weights,
            benchmark_weights=benchmark_weights,
            annualization_basis=annualization_basis,
        )
        if active_inputs is None:
            return _empty_attribution_set(
                attribution_type=attribution_type,
                metric=metric,
                grouping_dimension=grouping_dimension,
                quality_flags=flags + ["active_risk:alignment_empty"],
            )
        calculation_inputs = active_inputs

    if len(calculation_inputs.metric_series.dropna()) < 2:
        return _empty_attribution_set(
            attribution_type=attribution_type,
            metric=metric,
            grouping_dimension=grouping_dimension,
            quality_flags=flags + ["series:insufficient_observations"],
        )

    rows = _component_decomposition(
        group_matrix=calculation_inputs.group_matrix,
        metric_series=calculation_inputs.metric_series,
        total_value=calculation_inputs.risk_total,
        annualization_basis=annualization_basis,
    )
    return _reconciled_attribution_set(
        attribution_type=attribution_type,
        metric=metric,
        grouping_dimension=grouping_dimension,
        risk_total=calculation_inputs.risk_total,
        contributors=_attribution_contributors(rows=rows, group_labels=group_labels),
        quality_flags=flags,
    )


def _source_frames(request: HistoricalAttributionStatelessInput) -> _AttributionSourceFrames:
    return _AttributionSourceFrames(
        returns_df=_returns_df(request.returns),
        benchmark_df=_returns_df(request.benchmark_returns),
        exposure_df=_exposure_df(request.exposure_history),
        benchmark_exposure_df=_exposure_df(request.benchmark_exposure_history),
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


def _requires_benchmark_attribution(options: AttributionOptions) -> bool:
    return "ACTIVE_RISK" in options.attribution_types or "TRACKING_ERROR" in options.metrics


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


def _period_attribution_sets(
    *,
    options: AttributionOptions,
    frames: _AttributionSourceFrames,
    returns_series: pd.Series,
    benchmark_series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[AttributionSetResult]:
    period_sets: list[AttributionSetResult] = []
    requires_benchmark_attribution = _requires_benchmark_attribution(options)

    for grouping_dimension in options.grouping_dimensions:
        weights, labels, flags = _pivot_exposure(
            frames.exposure_df,
            start=start,
            end=end,
            grouping_dimension=grouping_dimension,
        )
        if requires_benchmark_attribution:
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
                    _build_attribution_set(
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


def _calculate_period_attribution(
    *,
    period: RiskRequestPeriod,
    request: HistoricalAttributionStatelessInput,
    frames: _AttributionSourceFrames,
    open_timestamp: pd.Timestamp,
    options: AttributionOptions,
) -> tuple[str, HistoricalAttributionPeriodResult]:
    start_date, end_date, start, end = _resolved_period_window(
        period=period,
        request=request,
        open_date=open_timestamp,
    )
    name = _period_name(period)
    returns_series = _window_returns(frames.returns_df, start, end) / 100.0
    benchmark_series = (
        _window_returns(frames.benchmark_df, start, end) / 100.0
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
        attribution_sets=_period_attribution_sets(
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
    frames = _source_frames(request)
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
