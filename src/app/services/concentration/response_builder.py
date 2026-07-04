from __future__ import annotations

from app.contracts.concentration import (
    ConcentrationResponse,
    ConcentrationRiskProxy,
    IssuerConcentration,
    SinglePositionConcentration,
    TopIssuerDriver,
    TopPositionDriver,
)
from app.service_metadata import SERVICE_NAME
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_concentration_response,
)
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
    TopIssuerDriverValue,
    TopPositionDriverValue,
)
from app.services.concentration.math import (
    _coverage_ratio,
    _round,
    _uncovered_count,
)
from app.services.concentration.response_metrics import (
    IssuerConcentrationMetrics,
    PositionConcentrationMetrics,
    issuer_metrics,
    position_metrics,
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


def _risk_proxy(position_metrics: PositionConcentrationMetrics) -> ConcentrationRiskProxy:
    return ConcentrationRiskProxy(
        hhi_current=_round(position_metrics.hhi_current),
        hhi_proposed=_round(position_metrics.hhi_proposed),
        hhi_delta=_round(position_metrics.hhi_proposed - position_metrics.hhi_current),
    )


def _top_position_driver(driver: TopPositionDriverValue) -> TopPositionDriver:
    return TopPositionDriver(
        security_id=driver.security_id,
        security_name=driver.security_name,
        weight=driver.weight,
    )


def _top_issuer_driver(driver: TopIssuerDriverValue) -> TopIssuerDriver:
    return TopIssuerDriver(
        issuer_id=driver.issuer_id,
        issuer_name=driver.issuer_name,
        weight=driver.weight,
    )


def _single_position_concentration(
    *,
    payload: ConcentrationComputationInput,
    position_metrics: PositionConcentrationMetrics,
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
        top_position_current=_top_position_driver(position_metrics.driver_current),
        top_position_proposed=_top_position_driver(position_metrics.driver_proposed),
    )


def _issuer_concentration(
    *,
    payload: ConcentrationComputationInput,
    issuer_metrics: IssuerConcentrationMetrics,
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
        top_issuer_current=_top_issuer_driver(issuer_metrics.driver_current),
        top_issuer_proposed=_top_issuer_driver(issuer_metrics.driver_proposed),
    )


def _build_response(payload: ConcentrationComputationInput) -> ConcentrationResponse:
    concentration_position_metrics = position_metrics(payload)
    concentration_issuer_metrics = issuer_metrics(payload)
    _record_concentration_supportability(payload)

    return ConcentrationResponse(
        source_service=SERVICE_NAME,
        input_mode=payload.input_mode,
        risk_proxy=_risk_proxy(concentration_position_metrics),
        single_position_concentration=_single_position_concentration(
            payload=payload,
            position_metrics=concentration_position_metrics,
        ),
        issuer_concentration=_issuer_concentration(
            payload=payload,
            issuer_metrics=concentration_issuer_metrics,
        ),
        valuation_context=payload.valuation_context,
        metadata=payload.metadata,
    )
