from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.contracts.risk import ReturnPoint
from app.contracts.rolling import ROLLING_BENCHMARK_METRICS, RollingStatefulInput
from app.services.core_risk_free_series import (
    build_risk_free_series_request,
    to_risk_free_return_points,
)
from app.services.rolling_metric_series import ROLLING_SHARPE_METRIC
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import (
    extract_required_portfolio_returns,
    to_return_points,
)
from app.upstream_errors import UpstreamServiceError, missing_upstream_data


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


class LotusCoreClientProtocol(Protocol):
    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_risk_free_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_risk_free_coverage(
        self,
        *,
        currency: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class StatefulSourceResponses:
    source_payload: dict[str, Any]
    source_response: dict[str, Any]
    risk_free_request: dict[str, Any] | None
    risk_free_response: dict[str, Any] | None


@dataclass(frozen=True)
class ResolvedStatefulRollingInputs:
    stateful: RollingStatefulInput
    include_risk_free: bool
    source_payload: dict[str, Any]
    risk_free_request: dict[str, Any] | None
    portfolio_points: list[ReturnPoint]
    benchmark_points: list[ReturnPoint]
    risk_free_points: list[ReturnPoint]


@dataclass(frozen=True)
class ResolvedRiskFreeDependency:
    request: dict[str, Any] | None
    points: list[ReturnPoint]


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


def build_stateful_source_request(stateful: RollingStatefulInput) -> dict[str, Any]:
    include_benchmark = any(
        metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics
    )
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=include_benchmark,
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )


def explicit_window_bounds(source_payload: dict[str, Any]) -> tuple[date, date] | None:
    window = source_payload.get("window")
    if not isinstance(window, dict):
        return None
    if window.get("mode") != "EXPLICIT":
        return None

    raw_start = window.get("from_date")
    raw_end = window.get("to_date")
    if not isinstance(raw_start, str) or not isinstance(raw_end, str):
        return None
    return date.fromisoformat(raw_start), date.fromisoformat(raw_end)


async def _resolve_reporting_currency(
    *,
    stateful: RollingStatefulInput,
    include_risk_free: bool,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> str | None:
    if stateful.reporting_currency:
        return stateful.reporting_currency
    if not include_risk_free:
        return None
    if core_client is None:
        raise ValueError(
            "reporting_currency is required for rolling Sharpe in stateful mode when lotus-core is unavailable"
        )

    snapshot = await core_client.get_core_snapshot(
        portfolio_id=stateful.portfolio_id,
        request_payload={
            "snapshot_mode": "BASELINE",
            "as_of_date": stateful.as_of_date.isoformat(),
            "sections": ["portfolio_totals"],
        },
        correlation_id=correlation_id,
    )
    valuation_context = snapshot.get("valuation_context")
    if not isinstance(valuation_context, dict):
        raise ValueError("lotus-core core-snapshot payload missing valuation_context")
    resolved_reporting_currency = valuation_context.get("reporting_currency")
    if not isinstance(resolved_reporting_currency, str) or not resolved_reporting_currency:
        resolved_reporting_currency = valuation_context.get("portfolio_currency")
    if not isinstance(resolved_reporting_currency, str) or not resolved_reporting_currency:
        raise ValueError(
            "lotus-core core-snapshot payload missing portfolio/reporting currency required for rolling Sharpe"
        )
    return resolved_reporting_currency


def _requires_risk_free(stateful: RollingStatefulInput) -> bool:
    return ROLLING_SHARPE_METRIC in stateful.rolling_options.metrics


def _requires_benchmark(stateful: RollingStatefulInput) -> bool:
    return any(metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics)


async def _fetch_stateful_source_responses(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
    include_risk_free: bool,
    reporting_currency: str | None,
) -> StatefulSourceResponses:
    source_payload = build_stateful_source_request(stateful)
    explicit_window = explicit_window_bounds(source_payload)
    risk_free_request: dict[str, Any] | None = None
    risk_free_response: dict[str, Any] | None = None

    if include_risk_free and core_client is None:
        raise ValueError(
            "lotus-core client is required for rolling Sharpe stateful risk-free sourcing"
        )

    if include_risk_free and explicit_window is not None:
        if reporting_currency is None:
            raise ValueError("reporting currency is required for rolling risk-free sourcing")
        checked_core_client = core_client
        if checked_core_client is None:
            raise ValueError("lotus-core client is required for rolling risk-free sourcing")
        risk_free_request = build_risk_free_series_request(
            currency=reporting_currency,
            as_of_date=stateful.as_of_date,
            start_date=explicit_window[0],
            end_date=explicit_window[1],
        )
        source_response, risk_free_response = await asyncio.gather(
            performance_client.get_returns_series(
                request_payload=source_payload,
                correlation_id=correlation_id,
            ),
            checked_core_client.get_risk_free_series(
                request_payload=risk_free_request,
                correlation_id=correlation_id,
            ),
        )
    else:
        source_response = await performance_client.get_returns_series(
            request_payload=source_payload,
            correlation_id=correlation_id,
        )

    return StatefulSourceResponses(
        source_payload=source_payload,
        source_response=source_response,
        risk_free_request=risk_free_request,
        risk_free_response=risk_free_response,
    )


def _benchmark_points_or_raise(
    series: dict[str, Any],
    *,
    include_benchmark: bool,
) -> list[ReturnPoint]:
    benchmark_points = to_return_points(series.get("benchmark_returns"))
    if include_benchmark and not benchmark_points:
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=(
                "lotus-performance returns-series returned no benchmark returns for "
                "requested rolling benchmark metrics"
            ),
        )
    return benchmark_points


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
    risk_free_points = (
        to_risk_free_return_points(
            risk_free_response,
            annualization_basis=annualization_basis,
        )
        if include_risk_free and risk_free_response is not None
        else []
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
    raise missing_upstream_data(
        service="lotus-core",
        operation="/integration/reference/risk-free-series",
        message=(
            "lotus-core risk-free-series returned no usable risk-free returns for "
            "requested rolling Sharpe"
        ),
        details=coverage_details,
    )


async def _resolve_risk_free_dependency(
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


async def resolve_stateful_rolling_inputs(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None = None,
    correlation_id: str | None,
) -> ResolvedStatefulRollingInputs:
    include_risk_free = _requires_risk_free(stateful)
    resolved_reporting_currency = await _resolve_reporting_currency(
        stateful=stateful,
        include_risk_free=include_risk_free,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    if resolved_reporting_currency != stateful.reporting_currency:
        stateful = stateful.model_copy(update={"reporting_currency": resolved_reporting_currency})

    source_responses = await _fetch_stateful_source_responses(
        stateful,
        performance_client=performance_client,
        core_client=core_client,
        correlation_id=correlation_id,
        include_risk_free=include_risk_free,
        reporting_currency=resolved_reporting_currency,
    )
    series, portfolio_points = extract_required_portfolio_returns(source_responses.source_response)
    benchmark_points = _benchmark_points_or_raise(
        series,
        include_benchmark=_requires_benchmark(stateful),
    )
    risk_free_dependency = await _resolve_risk_free_dependency(
        include_risk_free=include_risk_free,
        source_responses=source_responses,
        core_client=core_client,
        reporting_currency=resolved_reporting_currency,
        stateful=stateful,
        portfolio_points=portfolio_points,
        correlation_id=correlation_id,
    )
    return ResolvedStatefulRollingInputs(
        stateful=stateful,
        include_risk_free=include_risk_free,
        source_payload=source_responses.source_payload,
        risk_free_request=risk_free_dependency.request,
        portfolio_points=portfolio_points,
        benchmark_points=benchmark_points,
        risk_free_points=risk_free_dependency.points,
    )
