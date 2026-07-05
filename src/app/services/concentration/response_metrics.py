from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.concentration import (
    IssuerCoverageStatus,
)
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
    TopIssuerDriverValue,
    TopPositionDriverValue,
)
from app.services.concentration.math import (
    _compute_hhi,
    _single_position_metrics,
    _top_issuer_driver,
    _top_position_driver,
)


class _WeightedValue(Protocol):
    value: float  # monetary-float-allow: concentration exposure value, not money.


@dataclass(frozen=True)
class PositionConcentrationMetrics:
    hhi_current: float
    hhi_proposed: float
    top_current: float
    top_proposed: float
    top_n_current: float
    top_n_proposed: float
    driver_current: TopPositionDriverValue
    driver_proposed: TopPositionDriverValue


@dataclass(frozen=True)
class IssuerConcentrationMetrics:
    hhi_current: float
    hhi_proposed: float
    top_current: float
    top_proposed: float
    driver_current: TopIssuerDriverValue
    driver_proposed: TopIssuerDriverValue
    coverage_status: IssuerCoverageStatus


def _values(entries: Sequence[_WeightedValue]) -> list[float]:
    return [
        float(entry.value)  # monetary-float-allow: concentration exposure value, not money.
        for entry in entries
    ]


def issuer_coverage_status(payload: ConcentrationComputationInput) -> IssuerCoverageStatus:
    if payload.total_position_count_current <= 0 and payload.total_position_count_proposed <= 0:
        return IssuerCoverageStatus.UNAVAILABLE
    if (
        payload.covered_position_count_current == payload.total_position_count_current
        and payload.covered_position_count_proposed == payload.total_position_count_proposed
    ):
        return IssuerCoverageStatus.COMPLETE
    if payload.covered_position_count_current > 0 or payload.covered_position_count_proposed > 0:
        return IssuerCoverageStatus.PARTIAL
    return IssuerCoverageStatus.UNAVAILABLE


def position_metrics(payload: ConcentrationComputationInput) -> PositionConcentrationMetrics:
    current_values = _values(payload.current_positions)
    proposed_values = _values(payload.proposed_positions)
    current_hhi = _compute_hhi(current_values)
    fallback_to_current = payload.use_current_state_when_proposed_empty and not proposed_values
    proposed_hhi = current_hhi if fallback_to_current else _compute_hhi(proposed_values)

    current_top, current_top_n = _single_position_metrics(current_values, top_n=payload.top_n)
    if fallback_to_current:
        proposed_top, proposed_top_n = current_top, current_top_n
    else:
        proposed_top, proposed_top_n = _single_position_metrics(
            proposed_values, top_n=payload.top_n
        )

    current_top_position = _top_position_driver(payload.current_positions)
    proposed_top_position = (
        current_top_position
        if fallback_to_current
        else _top_position_driver(payload.proposed_positions)
    )
    return PositionConcentrationMetrics(
        hhi_current=current_hhi,
        hhi_proposed=proposed_hhi,
        top_current=current_top,
        top_proposed=proposed_top,
        top_n_current=current_top_n,
        top_n_proposed=proposed_top_n,
        driver_current=current_top_position,
        driver_proposed=proposed_top_position,
    )


def issuer_metrics(payload: ConcentrationComputationInput) -> IssuerConcentrationMetrics:
    current_issuer_values = _values(payload.current_issuers)
    proposed_issuer_values = _values(payload.proposed_issuers)
    current_issuer_hhi = _compute_hhi(current_issuer_values)
    fallback_to_current = (
        payload.use_current_state_when_proposed_empty and not proposed_issuer_values
    )
    proposed_issuer_hhi = (
        current_issuer_hhi if fallback_to_current else _compute_hhi(proposed_issuer_values)
    )

    current_issuer_top, _ = _single_position_metrics(current_issuer_values, top_n=1)
    if fallback_to_current:
        proposed_issuer_top = current_issuer_top
    else:
        proposed_issuer_top, _ = _single_position_metrics(proposed_issuer_values, top_n=1)

    current_top_issuer = _top_issuer_driver(payload.current_issuers)
    proposed_top_issuer = (
        current_top_issuer if fallback_to_current else _top_issuer_driver(payload.proposed_issuers)
    )
    return IssuerConcentrationMetrics(
        hhi_current=current_issuer_hhi,
        hhi_proposed=proposed_issuer_hhi,
        top_current=current_issuer_top,
        top_proposed=proposed_issuer_top,
        driver_current=current_top_issuer,
        driver_proposed=proposed_top_issuer,
        coverage_status=issuer_coverage_status(payload),
    )


__all__ = [
    "IssuerConcentrationMetrics",
    "PositionConcentrationMetrics",
    "issuer_coverage_status",
    "issuer_metrics",
    "position_metrics",
]
