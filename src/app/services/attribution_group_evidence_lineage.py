"""Deterministic, authorization-free calculation identity for group evidence."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from app.contracts.attribution import AttributionMetric, AttributionType, GroupingDimension
from app.services.attribution_group_evidence import (
    GroupEvidencePack,
    group_evidence_applies_to_set,
)


def canonical_group_evidence_payload(
    evidence: Mapping[str, Mapping[GroupingDimension, GroupEvidencePack]] | None,
    *,
    attribution_types: Collection[AttributionType],
    metrics: Collection[AttributionMetric],
) -> dict[str, Any]:
    """Capture the validated producer observations that reached covariance.

    This deliberately differs from request fingerprints, which identify the
    outgoing contribution calls rather than their returned calculation facts.
    """
    if not evidence:
        return {}
    if not _has_supported_empirical_set(
        attribution_types=attribution_types,
        metrics=metrics,
    ):
        return {}
    return {
        period_name: {
            dimension: {
                "expected_group_keys": list(pack.expected_group_keys),
                "degradation_flags": list(pack.degradation_flags),
                "series_by_group": _empirical_series_payload(pack),
            }
            for dimension, pack in sorted(per_dimension.items())
        }
        for period_name, per_dimension in sorted(evidence.items())
    }


def _has_supported_empirical_set(
    *,
    attribution_types: Collection[AttributionType],
    metrics: Collection[AttributionMetric],
) -> bool:
    return any(
        group_evidence_applies_to_set(attribution_type=attribution_type, metric=metric)
        for attribution_type in attribution_types
        for metric in metrics
    )


def _empirical_series_payload(pack: GroupEvidencePack) -> dict[str, Any]:
    """Fingerprint observations only when the engine admits them to covariance."""
    if not pack.empirical:
        return {}
    return {
        group_key: {
            "currency": series.currency,
            "observations": [
                {
                    "date": observation.observation_date.isoformat(),
                    "return_pp": observation.return_pp,
                    "weight_ratio": observation.weight_ratio,
                }
                for observation in series.observations
            ],
        }
        for group_key, series in sorted(pack.series_by_group.items())
    }


__all__ = ["canonical_group_evidence_payload"]
