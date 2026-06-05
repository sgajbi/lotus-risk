from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.concentration import (
    ConcentrationResponse,
    ConcentrationRiskProxy,
    IssuerConcentration,
    IssuerCoverageStatus,
    SinglePositionConcentration,
    TopIssuerDriver,
    TopPositionDriver,
)
from app.service_metadata import SERVICE_NAME
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_concentration_response,
)
from app.services.concentration.datamodels import ConcentrationComputationInput
from app.services.concentration.math import (
    _coverage_ratio,
    _compute_hhi,
    _round,
    _single_position_metrics,
    _top_issuer_driver,
    _top_position_driver,
    _uncovered_count,
)


class _WeightedValue(Protocol):
    value: float


@dataclass(frozen=True)
class _PositionConcentrationMetrics:
    hhi_current: float
    hhi_proposed: float
    top_current: float
    top_proposed: float
    top_n_current: float
    top_n_proposed: float
    driver_current: TopPositionDriver
    driver_proposed: TopPositionDriver


@dataclass(frozen=True)
class _IssuerConcentrationMetrics:
    hhi_current: float
    hhi_proposed: float
    top_current: float
    top_proposed: float
    driver_current: TopIssuerDriver
    driver_proposed: TopIssuerDriver
    coverage_status: IssuerCoverageStatus


def _values(entries: Sequence[_WeightedValue]) -> list[float]:
    return [float(entry.value) for entry in entries]


def _issuer_coverage_status(payload: ConcentrationComputationInput) -> IssuerCoverageStatus:
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


def _position_metrics(payload: ConcentrationComputationInput) -> _PositionConcentrationMetrics:
    current_values = _values(payload.current_positions)
    proposed_values = _values(payload.proposed_positions)
    current_hhi = _compute_hhi(current_values)
    proposed_hhi = _compute_hhi(proposed_values) if proposed_values else current_hhi

    current_top, current_top_n = _single_position_metrics(current_values, top_n=payload.top_n)
    if proposed_values:
        proposed_top, proposed_top_n = _single_position_metrics(
            proposed_values, top_n=payload.top_n
        )
    else:
        proposed_top, proposed_top_n = current_top, current_top_n

    current_top_position = _top_position_driver(payload.current_positions)
    proposed_top_position = (
        _top_position_driver(payload.proposed_positions)
        if payload.proposed_positions
        else current_top_position
    )
    return _PositionConcentrationMetrics(
        hhi_current=current_hhi,
        hhi_proposed=proposed_hhi,
        top_current=current_top,
        top_proposed=proposed_top,
        top_n_current=current_top_n,
        top_n_proposed=proposed_top_n,
        driver_current=current_top_position,
        driver_proposed=proposed_top_position,
    )


def _issuer_metrics(payload: ConcentrationComputationInput) -> _IssuerConcentrationMetrics:
    current_issuer_values = _values(payload.current_issuers)
    proposed_issuer_values = _values(payload.proposed_issuers)
    current_issuer_hhi = _compute_hhi(current_issuer_values)
    proposed_issuer_hhi = (
        _compute_hhi(proposed_issuer_values) if proposed_issuer_values else current_issuer_hhi
    )

    current_issuer_top, _ = _single_position_metrics(current_issuer_values, top_n=1)
    if proposed_issuer_values:
        proposed_issuer_top, _ = _single_position_metrics(proposed_issuer_values, top_n=1)
    else:
        proposed_issuer_top = current_issuer_top

    current_top_issuer = _top_issuer_driver(payload.current_issuers)
    proposed_top_issuer = (
        _top_issuer_driver(payload.proposed_issuers)
        if payload.proposed_issuers
        else current_top_issuer
    )
    return _IssuerConcentrationMetrics(
        hhi_current=current_issuer_hhi,
        hhi_proposed=proposed_issuer_hhi,
        top_current=current_issuer_top,
        top_proposed=proposed_issuer_top,
        driver_current=current_top_issuer,
        driver_proposed=proposed_top_issuer,
        coverage_status=_issuer_coverage_status(payload),
    )


def _record_concentration_supportability(payload: ConcentrationComputationInput) -> None:
    calculation_supportability = supportability_from_concentration_response(
        covered_position_count_current=payload.covered_position_count_current,
        covered_position_count_proposed=payload.covered_position_count_proposed,
        total_position_count_current=payload.total_position_count_current,
        total_position_count_proposed=payload.total_position_count_proposed,
        issuer_note=payload.issuer_note,
    )
    if payload.metadata is not None:
        payload.metadata.calculation_supportability = calculation_supportability
    record_operation_supportability(
        operation="risk/concentration",
        supportability=calculation_supportability,
    )


def _risk_proxy(position_metrics: _PositionConcentrationMetrics) -> ConcentrationRiskProxy:
    return ConcentrationRiskProxy(
        hhi_current=_round(position_metrics.hhi_current),
        hhi_proposed=_round(position_metrics.hhi_proposed),
        hhi_delta=_round(position_metrics.hhi_proposed - position_metrics.hhi_current),
    )


def _single_position_concentration(
    *,
    payload: ConcentrationComputationInput,
    position_metrics: _PositionConcentrationMetrics,
) -> SinglePositionConcentration:
    return SinglePositionConcentration(
        top_position_weight_current=_round(position_metrics.top_current),
        top_position_weight_proposed=_round(position_metrics.top_proposed),
        top_position_weight_delta=_round(
            position_metrics.top_proposed - position_metrics.top_current
        ),
        top_n_cumulative_weight_current=_round(position_metrics.top_n_current),
        top_n_cumulative_weight_proposed=_round(position_metrics.top_n_proposed),
        top_n_cumulative_weight_delta=_round(
            position_metrics.top_n_proposed - position_metrics.top_n_current
        ),
        top_n=payload.top_n,
        top_position_current=position_metrics.driver_current,
        top_position_proposed=position_metrics.driver_proposed,
    )


def _issuer_concentration(
    *,
    payload: ConcentrationComputationInput,
    issuer_metrics: _IssuerConcentrationMetrics,
) -> IssuerConcentration:
    return IssuerConcentration(
        hhi_current=_round(issuer_metrics.hhi_current),
        hhi_proposed=_round(issuer_metrics.hhi_proposed),
        hhi_delta=_round(issuer_metrics.hhi_proposed - issuer_metrics.hhi_current),
        top_issuer_weight_current=_round(issuer_metrics.top_current),
        top_issuer_weight_proposed=_round(issuer_metrics.top_proposed),
        top_issuer_weight_delta=_round(issuer_metrics.top_proposed - issuer_metrics.top_current),
        coverage_status=issuer_metrics.coverage_status,
        covered_position_count_current=payload.covered_position_count_current,
        covered_position_count_proposed=payload.covered_position_count_proposed,
        total_position_count_current=payload.total_position_count_current,
        total_position_count_proposed=payload.total_position_count_proposed,
        uncovered_position_count_current=_uncovered_count(
            payload.covered_position_count_current,
            payload.total_position_count_current,
        ),
        uncovered_position_count_proposed=_uncovered_count(
            payload.covered_position_count_proposed,
            payload.total_position_count_proposed,
        ),
        coverage_ratio_current=_coverage_ratio(
            payload.covered_position_count_current,
            payload.total_position_count_current,
        ),
        coverage_ratio_proposed=_coverage_ratio(
            payload.covered_position_count_proposed,
            payload.total_position_count_proposed,
        ),
        note=payload.issuer_note,
        top_issuer_current=issuer_metrics.driver_current,
        top_issuer_proposed=issuer_metrics.driver_proposed,
    )


def _build_response(payload: ConcentrationComputationInput) -> ConcentrationResponse:
    position_metrics = _position_metrics(payload)
    issuer_metrics = _issuer_metrics(payload)
    _record_concentration_supportability(payload)

    return ConcentrationResponse(
        source_service=SERVICE_NAME,
        input_mode=payload.input_mode,
        risk_proxy=_risk_proxy(position_metrics),
        single_position_concentration=_single_position_concentration(
            payload=payload,
            position_metrics=position_metrics,
        ),
        issuer_concentration=_issuer_concentration(
            payload=payload,
            issuer_metrics=issuer_metrics,
        ),
        valuation_context=payload.valuation_context,
        metadata=payload.metadata,
    )
