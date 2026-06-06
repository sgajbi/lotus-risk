from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import TypedDict

import numpy as np
import pandas as pd

from app.contracts.attribution import AttributionType


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


def component_decomposition(
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
        decomposition.append(
            _component_decomposition_row(
                group_key=str(group_key),
                group_series=group_matrix[group_key],
                group_weight_average=float(metric_mean[group_key]),
                metric_series=metric_series,
                contribution_denominator=contribution_denominator,
                annualization_basis=annualization_basis,
                metric_std=std,
            )
        )
    return decomposition


def _component_decomposition_row(
    *,
    group_key: str,
    group_series: pd.Series,
    group_weight_average: float,
    metric_series: pd.Series,
    contribution_denominator: float,
    annualization_basis: int,
    metric_std: float,
) -> DecompositionRow:
    cov = float(np.cov(group_series, metric_series, ddof=1)[0, 1])
    component = float((cov / metric_std) * sqrt(annualization_basis))
    marginal = (
        float(component / group_weight_average)
        if not np.isclose(group_weight_average, 0.0)
        else None
    )
    percent = (
        float(component / contribution_denominator)
        if not np.isclose(contribution_denominator, 0.0)
        else None
    )
    return {
        "group_key": group_key,
        "weight_average": group_weight_average,
        "marginal_contribution": marginal,
        "component_contribution": component,
        "percent_contribution": percent,
    }


def attribution_calculation_inputs(
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
