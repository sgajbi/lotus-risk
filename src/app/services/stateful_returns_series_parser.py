from __future__ import annotations

from calendar import monthrange
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


def to_return_points(series: Any, *, frequency: str = "DAILY") -> list[ReturnPoint]:
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
        if not _date_matches_frequency(parsed_date, frequency=frequency):
            if frequency == "DAILY":
                # Performance's daily contract may carry calendar observations;
                # Risk consumes the trading-day subset without inventing a holiday calendar.
                continue
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="Return date from lotus-performance does not match frequency",
                details={"field": "date", "frequency": frequency},
            )
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


def _date_matches_frequency(value: date, *, frequency: str) -> bool:
    if frequency == "DAILY":
        return is_trading_day(value)
    if frequency == "WEEKLY":
        return value.weekday() == 4
    if frequency == "MONTHLY":
        return value.day == monthrange(value.year, value.month)[1]
    return False


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
    *,
    frequency: str = "DAILY",
) -> tuple[dict[str, Any], list[ReturnPoint]]:
    series = extract_series_payload(source_response)
    portfolio_points = to_return_points(
        series.get("portfolio_returns"),
        frequency=frequency,
    )
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
    frequency: str,
    metric_basis: str,
    requested_window: dict[str, Any] | None = None,
    returned_points: list[ReturnPoint] | None = None,
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
        frequency=frequency,
        metric_basis=metric_basis,
    )
    _validate_stateful_provenance(provenance)
    if returned_points is not None and evidence.returned_points != len(returned_points):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance coverage does not match consumed portfolio returns",
            details={"field": "diagnostics.coverage.returned_points"},
        )
    if requested_window is not None:
        _validate_resolved_window(
            source_response,
            requested_window=requested_window,
            as_of_date=as_of_date,
        )
        if returned_points is not None:
            _validate_returned_points_within_window(
                source_response,
                returned_points,
                frequency=frequency,
            )
    return evidence


def normalize_return_points_to_resolved_window(
    source_response: dict[str, Any],
    returned_points: list[ReturnPoint],
    *,
    frequency: str,
) -> list[ReturnPoint]:
    """Use the admitted window end as a trailing partial bucket's effective date.

    Performance labels weekly and monthly buckets by their scheduled end.  A bucket
    built from observations through the admitted end can therefore have a later
    label.  Clamping only that accepted trailing label keeps the observation inside
    Risk's period filter while retaining the producer calculation identity.
    """
    _validate_returned_points_within_window(
        source_response,
        returned_points,
        frequency=frequency,
    )
    if frequency == "DAILY":
        return returned_points
    resolved_window = _mapping_or_empty(source_response.get("resolved_window"))
    try:
        end_date = date.fromisoformat(resolved_window["end_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _window_mismatch_error() from exc
    return [
        point.model_copy(update={"date": min(point.date, end_date)}) for point in returned_points
    ]


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
    frequency: str,
    metric_basis: str,
) -> None:
    expected_fields = {
        "portfolio_id": portfolio_id,
        "as_of_date": as_of_date.isoformat(),
        "frequency": frequency,
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


def _validate_resolved_window(
    source_response: dict[str, Any],
    *,
    requested_window: dict[str, Any],
    as_of_date: date,
) -> None:
    resolved_window = _mapping_or_empty(source_response.get("resolved_window"))
    mode = requested_window.get("mode")
    if mode == "EXPLICIT":
        _validate_explicit_window(resolved_window, requested_window=requested_window)
        return
    if mode == "RELATIVE":
        _validate_relative_window(
            resolved_window,
            requested_window=requested_window,
            as_of_date=as_of_date,
        )
        return
    _raise_window_mismatch()


def _validate_explicit_window(
    resolved_window: dict[str, Any],
    *,
    requested_window: dict[str, Any],
) -> None:
    expected = {
        "start_date": requested_window.get("from_date"),
        "end_date": requested_window.get("to_date"),
        "resolved_period_label": None,
    }
    if any(resolved_window.get(field) != value for field, value in expected.items()):
        _raise_window_mismatch()


def _validate_relative_window(
    resolved_window: dict[str, Any],
    *,
    requested_window: dict[str, Any],
    as_of_date: date,
) -> None:
    if resolved_window.get("resolved_period_label") != requested_window.get("period"):
        _raise_window_mismatch()
    raw_start = resolved_window.get("start_date")
    raw_end = resolved_window.get("end_date")
    try:
        start_date = date.fromisoformat(raw_start) if isinstance(raw_start, str) else None
        end_date = date.fromisoformat(raw_end) if isinstance(raw_end, str) else None
    except ValueError as exc:
        raise _window_mismatch_error() from exc
    if start_date is None or end_date != as_of_date or start_date > end_date:
        _raise_window_mismatch()


def _validate_returned_points_within_window(
    source_response: dict[str, Any],
    returned_points: list[ReturnPoint],
    *,
    frequency: str,
) -> None:
    resolved_window = _mapping_or_empty(source_response.get("resolved_window"))
    try:
        start_date = date.fromisoformat(resolved_window["start_date"])
        end_date = date.fromisoformat(resolved_window["end_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _window_mismatch_error() from exc
    if any(
        not _bucket_overlaps_window(
            point.date,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
        )
        for point in returned_points
    ):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/returns/series",
            message="lotus-performance portfolio return lies outside resolved window",
            details={"field": "series.portfolio_returns.date"},
        )


def _bucket_overlaps_window(
    bucket_end: date,
    *,
    frequency: str,
    start_date: date,
    end_date: date,
) -> bool:
    if frequency == "WEEKLY":
        bucket_start = date.fromordinal(max(date.min.toordinal(), bucket_end.toordinal() - 6))
    elif frequency == "MONTHLY":
        bucket_start = bucket_end.replace(day=1)
    else:
        bucket_start = bucket_end
    return bucket_start <= end_date and bucket_end >= start_date


def _raise_window_mismatch() -> None:
    raise _window_mismatch_error()


def _window_mismatch_error() -> ValueError:
    return invalid_upstream_payload(
        service="lotus-performance",
        operation="/integration/returns/series",
        message="lotus-performance returns-series resolved window does not match request",
        details={"field": "resolved_window"},
    )


def _mapping_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
