from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.downstream_authority import DownstreamAuthority
from app.contracts.risk import ReturnPoint
from app.contracts.rolling import RollingStatefulInput
from app.contracts.stateful_returns_source_evidence import StatefulReturnsSourceEvidence
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
    extract_stateful_returns_source_evidence,
    to_return_points,
)
from app.upstream_errors import missing_upstream_data


@dataclass(frozen=True)
class _ParsedRollingSourceSeries:
    portfolio_points: list[ReturnPoint]
    benchmark_points: list[ReturnPoint]
    evidence: StatefulReturnsSourceEvidence


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
    benchmark_points = to_return_points(series.get("benchmark_returns"), frequency="DAILY")
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
    stateful: RollingStatefulInput,
    source_payload: dict[str, Any],
    include_benchmark: bool,
) -> _ParsedRollingSourceSeries:
    series, portfolio_points = extract_required_portfolio_returns(
        source_response,
        frequency="DAILY",
    )
    return _ParsedRollingSourceSeries(
        portfolio_points=portfolio_points,
        benchmark_points=_benchmark_points_or_raise(
            series,
            include_benchmark=include_benchmark,
        ),
        evidence=extract_stateful_returns_source_evidence(
            source_response,
            portfolio_id=stateful.portfolio_id,
            as_of_date=stateful.as_of_date,
            frequency="DAILY",
            metric_basis=stateful.net_or_gross,
            requested_window=source_payload["window"],
            returned_points=portfolio_points,
        ),
    )


def _resolved_stateful_inputs(
    *,
    stateful: RollingStatefulInput,
    include_risk_free: bool,
    core_snapshot_request: dict[str, Any] | None,
    source_responses: StatefulSourceResponses,
    parsed_series: _ParsedRollingSourceSeries,
    risk_free_points: list[ReturnPoint],
) -> ResolvedStatefulRollingInputs:
    return ResolvedStatefulRollingInputs(
        stateful=stateful,
        include_risk_free=include_risk_free,
        source_payload=source_responses.source_payload,
        core_snapshot_request=core_snapshot_request,
        risk_free_request=source_responses.risk_free_request,
        portfolio_points=parsed_series.portfolio_points,
        benchmark_points=parsed_series.benchmark_points,
        risk_free_points=risk_free_points,
        source_returns_evidence=parsed_series.evidence,
    )


async def _resolve_rolling_source_series(
    *,
    dependency_selection: RollingStatefulDependencySelection,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    authority: DownstreamAuthority,
) -> _RollingSourceResolution:
    source_responses = await fetch_stateful_source_responses(
        dependency_selection.stateful,
        performance_client=performance_client,
        core_client=core_client,
        authority=authority,
        include_risk_free=dependency_selection.include_risk_free,
        reporting_currency=dependency_selection.reporting_currency,
    )
    parsed_series = _parse_stateful_source_series(
        source_responses.source_response,
        stateful=dependency_selection.stateful,
        source_payload=source_responses.source_payload,
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
    authority: DownstreamAuthority,
) -> list[ReturnPoint]:
    risk_free_dependency = await resolve_risk_free_dependency(
        include_risk_free=dependency_selection.include_risk_free,
        source_responses=source_responses,
        core_client=core_client,
        reporting_currency=dependency_selection.reporting_currency,
        stateful=dependency_selection.stateful,
        portfolio_points=portfolio_points,
        authority=authority,
    )
    return risk_free_dependency.points


async def resolve_stateful_rolling_inputs(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None = None,
    authority: DownstreamAuthority,
) -> ResolvedStatefulRollingInputs:
    dependency_selection = await resolve_stateful_dependency_selection(
        stateful,
        core_client=core_client,
        authority=authority,
    )
    source_resolution = await _resolve_rolling_source_series(
        dependency_selection=dependency_selection,
        performance_client=performance_client,
        core_client=core_client,
        authority=authority,
    )
    risk_free_points = await _resolve_rolling_risk_free_dependency(
        dependency_selection=dependency_selection,
        source_responses=source_resolution.source_responses,
        core_client=core_client,
        portfolio_points=source_resolution.parsed_series.portfolio_points,
        authority=authority,
    )
    return _resolved_stateful_inputs(
        stateful=dependency_selection.stateful,
        include_risk_free=dependency_selection.include_risk_free,
        core_snapshot_request=dependency_selection.core_snapshot_request,
        source_responses=source_resolution.source_responses,
        parsed_series=source_resolution.parsed_series,
        risk_free_points=risk_free_points,
    )
