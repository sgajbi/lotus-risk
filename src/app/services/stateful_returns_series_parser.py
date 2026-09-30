from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from app.contracts.risk import ReturnPoint
from app.contracts.stateful_returns_source_evidence import StatefulReturnsSourceEvidence
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data


def is_trading_day(value: date) -> bool:
    return value.weekday() < 5


def decimal_return_to_percentage_points(value: Any) -> float:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=f"Invalid return value from lotus-performance: {value}",
        ) from exc
    if not decimal_value.is_finite():
        # Decimal("NaN") and Decimal("Infinity") parse successfully and would flow into
        # covariance as non-finite floats; a non-finite return is producer corruption.
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=f"Non-finite return value from lotus-performance: {value}",
        )
    return float(decimal_value * Decimal("100"))


def to_return_points(series: Any) -> list[ReturnPoint]:
    if not isinstance(series, list):
        return []
    result: list[ReturnPoint] = []
    seen_dates: set[date] = set()
    for row in series:
        if not isinstance(row, dict):
            continue
        raw_date = row.get("date")
        if not isinstance(raw_date, str):
            continue
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="Invalid return date from lotus-performance",
                details={"field": "date"},
            ) from exc
        if not is_trading_day(parsed_date):
            continue
        if parsed_date in seen_dates:
            # Two observations for one date are contradictory economics: which return
            # applies is undecidable, and both entering covariance double-counts a day.
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="Duplicate return date from lotus-performance",
                details={"field": "date", "date": parsed_date.isoformat()},
            )
        seen_dates.add(parsed_date)
        result.append(
            ReturnPoint(
                date=parsed_date,
                value=decimal_return_to_percentage_points(row.get("return_value")),
            )
        )
    return result


def extract_series_payload(source_response: dict[str, Any]) -> dict[str, Any]:
    series = source_response.get("series")
    if not isinstance(series, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance returns-series payload missing 'series' object",
        )
    return series


def extract_required_portfolio_returns(
    source_response: dict[str, Any],
) -> tuple[dict[str, Any], list[ReturnPoint]]:
    series = extract_series_payload(source_response)
    portfolio_points = to_return_points(series.get("portfolio_returns"))
    if not portfolio_points:
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance returns-series returned no portfolio returns",
        )
    return series, portfolio_points


def extract_stateful_returns_source_evidence(
    source_response: dict[str, Any],
    *,
    portfolio_id: str,
    as_of_date: date,
    metric_basis: str,
) -> StatefulReturnsSourceEvidence:
    """Admit a Performance response only when its identity matches the Risk request.

    A valid JSON envelope and usable numbers do not establish that the evidence
    belongs to this portfolio, business date, or calculation.  Keep producer
    qualification intact so a caller cannot mistake a locally fresh last row
    for a current and complete source calculation.
    """
    provenance = _mapping_or_empty(source_response.get("provenance"))
    raw_evidence = _source_evidence_payload(source_response, provenance=provenance)
    try:
        evidence = StatefulReturnsSourceEvidence.model_validate(raw_evidence)
    except ValidationError as exc:
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance returns-series source qualification is invalid",
            details={"field": "source_qualification"},
        ) from exc

    _validate_source_request_identity(
        source_response,
        portfolio_id=portfolio_id,
        as_of_date=as_of_date,
        metric_basis=metric_basis,
    )
    _validate_stateful_provenance(provenance)
    return evidence


def _source_evidence_payload(
    source_response: dict[str, Any],
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    diagnostics = _mapping_or_empty(source_response.get("diagnostics"))
    coverage = _mapping_or_empty(diagnostics.get("coverage"))
    return {
        "source_service": source_response.get("source_service"),
        "calculation_id": source_response.get("calculation_id"),
        "contract_version": source_response.get("contract_version"),
        "input_fingerprint": provenance.get("input_fingerprint"),
        "calculation_hash": provenance.get("calculation_hash"),
        "freshness": diagnostics.get("freshness"),
        "requested_points": coverage.get("requested_points"),
        "returned_points": coverage.get("returned_points"),
        "missing_points": coverage.get("missing_points"),
        "coverage_ratio": coverage.get("coverage_ratio"),
    }


def _validate_source_request_identity(
    source_response: dict[str, Any],
    *,
    portfolio_id: str,
    as_of_date: date,
    metric_basis: str,
) -> None:
    expected_fields = {
        "portfolio_id": portfolio_id,
        "as_of_date": as_of_date.isoformat(),
        "frequency": "DAILY",
        "metric_basis": metric_basis,
    }
    for field, expected in expected_fields.items():
        if source_response.get(field) != expected:
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="lotus-performance returns-series identity does not match request",
                details={"field": field},
            )


def _validate_stateful_provenance(provenance: dict[str, Any]) -> None:
    if provenance.get("input_mode") != "stateful":
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance returns-series provenance does not match stateful request",
            details={"field": "provenance.input_mode"},
        )


def _mapping_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
