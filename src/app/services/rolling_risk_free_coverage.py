from __future__ import annotations

from datetime import date
from typing import Any

from app.services.rolling_stateful_models import LotusCoreClientProtocol
from app.upstream_errors import UpstreamServiceError


def _copy_int_detail(
    details: dict[str, Any],
    *,
    source: dict[str, Any],
    source_key: str,
    target_key: str,
) -> None:
    value = source.get(source_key)
    if isinstance(value, int):
        details[target_key] = value


def _copy_str_detail(
    details: dict[str, Any],
    *,
    source: dict[str, Any],
    source_key: str,
    target_key: str,
) -> None:
    value = source.get(source_key)
    if isinstance(value, str) and value:
        details[target_key] = value


def _copy_missing_dates_sample(details: dict[str, Any], *, source: dict[str, Any]) -> None:
    sample = source.get("missing_dates_sample")
    if isinstance(sample, list) and sample:
        details["risk_free_missing_dates_sample"] = [
            value for value in sample if isinstance(value, str)
        ]


def risk_free_coverage_request_payload(
    *,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    return {
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    }


def copy_risk_free_coverage_details(
    details: dict[str, Any],
    *,
    coverage: dict[str, Any],
) -> None:
    _copy_int_detail(
        details,
        source=coverage,
        source_key="total_points",
        target_key="risk_free_total_points",
    )
    _copy_int_detail(
        details,
        source=coverage,
        source_key="missing_dates_count",
        target_key="risk_free_missing_dates_count",
    )
    _copy_str_detail(
        details,
        source=coverage,
        source_key="observed_start_date",
        target_key="risk_free_observed_start_date",
    )
    _copy_str_detail(
        details,
        source=coverage,
        source_key="observed_end_date",
        target_key="risk_free_observed_end_date",
    )
    _copy_str_detail(
        details,
        source=coverage,
        source_key="request_fingerprint",
        target_key="risk_free_coverage_request_fingerprint",
    )
    _copy_missing_dates_sample(details, source=coverage)


async def get_risk_free_coverage_details(
    *,
    core_client: LotusCoreClientProtocol,
    currency: str,
    start_date: date,
    end_date: date,
    correlation_id: str | None,
) -> dict[str, Any]:
    details: dict[str, Any] = {"risk_free_currency": currency}
    try:
        coverage = await core_client.get_risk_free_coverage(
            currency=currency,
            request_payload=risk_free_coverage_request_payload(
                start_date=start_date,
                end_date=end_date,
            ),
            correlation_id=correlation_id,
        )
    except UpstreamServiceError:
        return details
    if not isinstance(coverage, dict):
        return details
    copy_risk_free_coverage_details(details, coverage=coverage)
    return details


__all__ = [
    "copy_risk_free_coverage_details",
    "get_risk_free_coverage_details",
    "risk_free_coverage_request_payload",
]
