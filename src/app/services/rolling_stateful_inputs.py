from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.contracts.risk import ReturnPoint
from app.contracts.rolling import RollingStatefulInput
from app.services.core_risk_free_series import build_risk_free_series_request
from app.services.rolling_risk_free_dependency import (
    get_risk_free_coverage_details,
    resolve_risk_free_dependency,
)
from app.services.rolling_stateful_dependency_selection import (
    RollingStatefulDependencySelection,
    requires_benchmark,
    resolve_stateful_dependency_selection,
)
from app.services.rolling_stateful_models import (
    LotusCoreClientProtocol,
    LotusPerformanceClientProtocol,
    ResolvedStatefulRollingInputs,
    StatefulSourceResponses,
)
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import (
    extract_required_portfolio_returns,
    to_return_points,
)
from app.upstream_errors import missing_upstream_data


@dataclass(frozen=True)
class _ParsedRollingSourceSeries:
    portfolio_points: list[ReturnPoint]
    benchmark_points: list[ReturnPoint]


@dataclass(frozen=True)
class _RollingSourceResolution:
    source_responses: StatefulSourceResponses
    parsed_series: _ParsedRollingSourceSeries


__all__ = [
    "LotusCoreClientProtocol",
    "LotusPerformanceClientProtocol",
    "ResolvedStatefulRollingInputs",
    "build_stateful_source_request",
    "explicit_window_bounds",
    "get_risk_free_coverage_details",
    "resolve_stateful_rolling_inputs",
]


def build_stateful_source_request(stateful: RollingStatefulInput) -> dict[str, Any]:
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=requires_benchmark(stateful),
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


def _explicit_risk_free_request(
    *,
    stateful: RollingStatefulInput,
    core_client: LotusCoreClientProtocol | None,
    include_risk_free: bool,
    explicit_window: tuple[date, date] | None,
    reporting_currency: str | None,
) -> tuple[dict[str, Any] | None, LotusCoreClientProtocol | None]:
    if not include_risk_free:
        return None, None
    if core_client is None:
        raise ValueError(
            "lotus-core client is required for rolling Sharpe stateful risk-free sourcing"
        )
    if explicit_window is None:
        return None, core_client
    if reporting_currency is None:
        raise ValueError("reporting currency is required for rolling risk-free sourcing")
    return (
        build_risk_free_series_request(
            currency=reporting_currency,
            as_of_date=stateful.as_of_date,
            start_date=explicit_window[0],
            end_date=explicit_window[1],
        ),
        core_client,
    )


async def _fetch_returns_and_risk_free_responses(
    *,
    source_payload: dict[str, Any],
    risk_free_request: dict[str, Any] | None,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if risk_free_request is not None and core_client is not None:
        source_response, risk_free_response = await asyncio.gather(
            performance_client.get_returns_series(
                request_payload=source_payload,
                correlation_id=correlation_id,
            ),
            core_client.get_risk_free_series(
                request_payload=risk_free_request,
                correlation_id=correlation_id,
            ),
        )
        return source_response, risk_free_response
    source_response = await performance_client.get_returns_series(
        request_payload=source_payload,
        correlation_id=correlation_id,
    )
    return source_response, None


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
    risk_free_request, checked_core_client = _explicit_risk_free_request(
        stateful=stateful,
        core_client=core_client,
        include_risk_free=include_risk_free,
        explicit_window=explicit_window,
        reporting_currency=reporting_currency,
    )
    source_response, risk_free_response = await _fetch_returns_and_risk_free_responses(
        source_payload=source_payload,
        risk_free_request=risk_free_request,
        performance_client=performance_client,
        core_client=checked_core_client,
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


def _parse_stateful_source_series(
    source_response: dict[str, Any],
    *,
    include_benchmark: bool,
) -> _ParsedRollingSourceSeries:
    series, portfolio_points = extract_required_portfolio_returns(source_response)
    return _ParsedRollingSourceSeries(
        portfolio_points=portfolio_points,
        benchmark_points=_benchmark_points_or_raise(
            series,
            include_benchmark=include_benchmark,
        ),
    )


def _resolved_stateful_inputs(
    *,
    stateful: RollingStatefulInput,
    include_risk_free: bool,
    source_responses: StatefulSourceResponses,
    parsed_series: _ParsedRollingSourceSeries,
    risk_free_points: list[ReturnPoint],
) -> ResolvedStatefulRollingInputs:
    return ResolvedStatefulRollingInputs(
        stateful=stateful,
        include_risk_free=include_risk_free,
        source_payload=source_responses.source_payload,
        risk_free_request=source_responses.risk_free_request,
        portfolio_points=parsed_series.portfolio_points,
        benchmark_points=parsed_series.benchmark_points,
        risk_free_points=risk_free_points,
    )


async def _resolve_rolling_source_series(
    *,
    dependency_selection: RollingStatefulDependencySelection,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> _RollingSourceResolution:
    source_responses = await _fetch_stateful_source_responses(
        dependency_selection.stateful,
        performance_client=performance_client,
        core_client=core_client,
        correlation_id=correlation_id,
        include_risk_free=dependency_selection.include_risk_free,
        reporting_currency=dependency_selection.reporting_currency,
    )
    parsed_series = _parse_stateful_source_series(
        source_responses.source_response,
        include_benchmark=requires_benchmark(dependency_selection.stateful),
    )
    return _RollingSourceResolution(
        source_responses=source_responses,
        parsed_series=parsed_series,
    )


async def _resolve_rolling_risk_free_dependency(
    *,
    dependency_selection: RollingStatefulDependencySelection,
    source_responses: StatefulSourceResponses,
    core_client: LotusCoreClientProtocol | None,
    portfolio_points: list[ReturnPoint],
    correlation_id: str | None,
) -> list[ReturnPoint]:
    risk_free_dependency = await resolve_risk_free_dependency(
        include_risk_free=dependency_selection.include_risk_free,
        source_responses=source_responses,
        core_client=core_client,
        reporting_currency=dependency_selection.reporting_currency,
        stateful=dependency_selection.stateful,
        portfolio_points=portfolio_points,
        correlation_id=correlation_id,
    )
    return risk_free_dependency.points


async def resolve_stateful_rolling_inputs(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None = None,
    correlation_id: str | None,
) -> ResolvedStatefulRollingInputs:
    dependency_selection = await resolve_stateful_dependency_selection(
        stateful,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    source_resolution = await _resolve_rolling_source_series(
        dependency_selection=dependency_selection,
        performance_client=performance_client,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    risk_free_points = await _resolve_rolling_risk_free_dependency(
        dependency_selection=dependency_selection,
        source_responses=source_resolution.source_responses,
        core_client=core_client,
        portfolio_points=source_resolution.parsed_series.portfolio_points,
        correlation_id=correlation_id,
    )
    return _resolved_stateful_inputs(
        stateful=dependency_selection.stateful,
        include_risk_free=dependency_selection.include_risk_free,
        source_responses=source_resolution.source_responses,
        parsed_series=source_resolution.parsed_series,
        risk_free_points=risk_free_points,
    )
