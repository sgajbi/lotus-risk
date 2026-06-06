from __future__ import annotations

from datetime import date
from typing import Any, NoReturn

from app.contracts.risk import ReturnPoint
from app.contracts.rolling import RollingStatefulInput
from app.services.core_risk_free_series import (
    build_risk_free_series_request,
    to_risk_free_return_points,
)
from app.services.rolling_stateful_models import (
    LotusCoreClientProtocol,
    ResolvedRiskFreeDependency,
    StatefulSourceResponses,
)
from app.upstream_errors import UpstreamServiceError, missing_upstream_data


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


def _risk_free_coverage_request_payload(*, start_date: date, end_date: date) -> dict[str, Any]:
    return {
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    }


def _copy_risk_free_coverage_details(
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
            request_payload=_risk_free_coverage_request_payload(
                start_date=start_date,
                end_date=end_date,
            ),
            correlation_id=correlation_id,
        )
    except UpstreamServiceError:
        return details
    if not isinstance(coverage, dict):
        return details
    _copy_risk_free_coverage_details(details, coverage=coverage)
    return details


async def _risk_free_response_or_none(
    *,
    include_risk_free: bool,
    risk_free_response: dict[str, Any] | None,
    core_client: LotusCoreClientProtocol | None,
    reporting_currency: str | None,
    stateful: RollingStatefulInput,
    portfolio_points: list[ReturnPoint],
    correlation_id: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not include_risk_free or risk_free_response is not None:
        return risk_free_response, None
    if core_client is None:
        raise ValueError("lotus-core client is required for rolling risk-free sourcing")
    if reporting_currency is None:
        raise ValueError("reporting currency is required for rolling risk-free sourcing")

    risk_free_request = build_risk_free_series_request(
        currency=reporting_currency,
        as_of_date=stateful.as_of_date,
        start_date=min(point.date for point in portfolio_points),
        end_date=max(point.date for point in portfolio_points),
    )
    fetched_response = await core_client.get_risk_free_series(
        request_payload=risk_free_request,
        correlation_id=correlation_id,
    )
    return fetched_response, risk_free_request


async def _risk_free_points_or_raise(
    *,
    include_risk_free: bool,
    risk_free_response: dict[str, Any] | None,
    core_client: LotusCoreClientProtocol | None,
    reporting_currency: str | None,
    annualization_basis: int,
    portfolio_points: list[ReturnPoint],
    correlation_id: str | None,
) -> list[ReturnPoint]:
    risk_free_points = _risk_free_points_from_response(
        include_risk_free=include_risk_free,
        risk_free_response=risk_free_response,
        annualization_basis=annualization_basis,
    )
    if not include_risk_free or risk_free_points:
        return risk_free_points
    if core_client is None:
        raise ValueError("lotus-core client is required for rolling risk-free sourcing")
    if reporting_currency is None:
        raise ValueError("reporting currency is required for rolling risk-free sourcing")
    coverage_details = await get_risk_free_coverage_details(
        core_client=core_client,
        currency=reporting_currency,
        start_date=min(point.date for point in portfolio_points),
        end_date=max(point.date for point in portfolio_points),
        correlation_id=correlation_id,
    )
    _raise_missing_risk_free_points(coverage_details)


def _risk_free_points_from_response(
    *,
    include_risk_free: bool,
    risk_free_response: dict[str, Any] | None,
    annualization_basis: int,
) -> list[ReturnPoint]:
    if not include_risk_free or risk_free_response is None:
        return []
    return to_risk_free_return_points(
        risk_free_response,
        annualization_basis=annualization_basis,
    )


def _raise_missing_risk_free_points(coverage_details: dict[str, Any]) -> NoReturn:
    raise missing_upstream_data(
        service="lotus-core",
        operation="/integration/reference/risk-free-series",
        message=(
            "lotus-core risk-free-series returned no usable risk-free returns for "
            "requested rolling Sharpe"
        ),
        details=coverage_details,
    )


async def resolve_risk_free_dependency(
    *,
    include_risk_free: bool,
    source_responses: StatefulSourceResponses,
    core_client: LotusCoreClientProtocol | None,
    reporting_currency: str | None,
    stateful: RollingStatefulInput,
    portfolio_points: list[ReturnPoint],
    correlation_id: str | None,
) -> ResolvedRiskFreeDependency:
    risk_free_response, fallback_risk_free_request = await _risk_free_response_or_none(
        include_risk_free=include_risk_free,
        risk_free_response=source_responses.risk_free_response,
        core_client=core_client,
        reporting_currency=reporting_currency,
        stateful=stateful,
        portfolio_points=portfolio_points,
        correlation_id=correlation_id,
    )
    return ResolvedRiskFreeDependency(
        request=source_responses.risk_free_request or fallback_risk_free_request,
        points=await _risk_free_points_or_raise(
            include_risk_free=include_risk_free,
            risk_free_response=risk_free_response,
            core_client=core_client,
            reporting_currency=reporting_currency,
            annualization_basis=stateful.rolling_options.annualization_basis,
            portfolio_points=portfolio_points,
            correlation_id=correlation_id,
        ),
    )
