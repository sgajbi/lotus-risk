from __future__ import annotations

from app.contracts.attribution import (
    AttributionContributor,
    AttributionMetric,
    AttributionSetResult,
    AttributionType,
    GroupingDimension,
)
from app.services.attribution_calculation import (
    AttributionCalculationInputs,
    DecompositionRow,
    component_decomposition,
)


def empty_attribution_set(
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


def calculated_attribution_set(
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


__all__ = ["calculated_attribution_set", "empty_attribution_set"]
