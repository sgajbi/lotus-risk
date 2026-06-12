from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.risk import ReturnPoint
from app.contracts.rolling import RollingStatefulInput
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
from app.services.rolling_stateful_source_responses import (
    build_stateful_source_request,
    explicit_window_bounds,
    fetch_stateful_source_responses,
)
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
    source_responses = await fetch_stateful_source_responses(
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
