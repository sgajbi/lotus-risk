from __future__ import annotations

from app.contracts.concentration import (
    ConcentrationResponse,
    ConcentrationRiskProxy,
    IssuerConcentration,
    SinglePositionConcentration,
    IssuerCoverageStatus,
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
from typing import Protocol
from collections.abc import Sequence


class _WeightedValue(Protocol):
    value: float


def _values(entries: Sequence[_WeightedValue]) -> list[float]:
    return [float(entry.value) for entry in entries]


def _build_response(payload: ConcentrationComputationInput) -> ConcentrationResponse:
    current_values = _values(payload.current_positions)
    proposed_values = _values(payload.proposed_positions)
    current_issuer_values = _values(payload.current_issuers)
    proposed_issuer_values = _values(payload.proposed_issuers)

    current_hhi = _compute_hhi(current_values)
    proposed_hhi = _compute_hhi(proposed_values) if proposed_values else current_hhi

    current_top, current_top_n = _single_position_metrics(current_values, top_n=payload.top_n)
    if proposed_values:
        proposed_top, proposed_top_n = _single_position_metrics(
            proposed_values, top_n=payload.top_n
        )
    else:
        proposed_top, proposed_top_n = current_top, current_top_n

    current_issuer_hhi = _compute_hhi(current_issuer_values)
    proposed_issuer_hhi = (
        _compute_hhi(proposed_issuer_values) if proposed_issuer_values else current_issuer_hhi
    )

    current_issuer_top, _ = _single_position_metrics(current_issuer_values, top_n=1)
    if proposed_issuer_values:
        proposed_issuer_top, _ = _single_position_metrics(proposed_issuer_values, top_n=1)
    else:
        proposed_issuer_top = current_issuer_top

    current_top_position = _top_position_driver(payload.current_positions)
    proposed_top_position = (
        _top_position_driver(payload.proposed_positions)
        if payload.proposed_positions
        else current_top_position
    )
    current_top_issuer = _top_issuer_driver(payload.current_issuers)
    proposed_top_issuer = (
        _top_issuer_driver(payload.proposed_issuers)
        if payload.proposed_issuers
        else current_top_issuer
    )

    coverage_status = IssuerCoverageStatus.UNAVAILABLE
    if payload.total_position_count_current > 0 or payload.total_position_count_proposed > 0:
        if (
            payload.covered_position_count_current == payload.total_position_count_current
            and payload.covered_position_count_proposed == payload.total_position_count_proposed
        ):
            coverage_status = IssuerCoverageStatus.COMPLETE
        elif (
            payload.covered_position_count_current > 0
            or payload.covered_position_count_proposed > 0
        ):
            coverage_status = IssuerCoverageStatus.PARTIAL

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

    return ConcentrationResponse(
        source_service=SERVICE_NAME,
        input_mode=payload.input_mode,
        risk_proxy=ConcentrationRiskProxy(
            hhi_current=_round(current_hhi),
            hhi_proposed=_round(proposed_hhi),
            hhi_delta=_round(proposed_hhi - current_hhi),
        ),
        single_position_concentration=SinglePositionConcentration(
            top_position_weight_current=_round(current_top),
            top_position_weight_proposed=_round(proposed_top),
            top_position_weight_delta=_round(proposed_top - current_top),
            top_n_cumulative_weight_current=_round(current_top_n),
            top_n_cumulative_weight_proposed=_round(proposed_top_n),
            top_n_cumulative_weight_delta=_round(proposed_top_n - current_top_n),
            top_n=payload.top_n,
            top_position_current=current_top_position,
            top_position_proposed=proposed_top_position,
        ),
        issuer_concentration=IssuerConcentration(
            hhi_current=_round(current_issuer_hhi),
            hhi_proposed=_round(proposed_issuer_hhi),
            hhi_delta=_round(proposed_issuer_hhi - current_issuer_hhi),
            top_issuer_weight_current=_round(current_issuer_top),
            top_issuer_weight_proposed=_round(proposed_issuer_top),
            top_issuer_weight_delta=_round(proposed_issuer_top - current_issuer_top),
            coverage_status=coverage_status,
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
            top_issuer_current=current_top_issuer,
            top_issuer_proposed=proposed_top_issuer,
        ),
        valuation_context=payload.valuation_context,
        metadata=payload.metadata,
    )
