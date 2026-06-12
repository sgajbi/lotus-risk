from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.contracts.attribution import (
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionStatefulInput,
    HistoricalAttributionStatelessInput,
)
from app.contracts.risk import ReturnPoint, RiskRequestScope
from app.services.attribution_exposure_history import (
    fetch_stateful_exposure_history,
)
from app.services.attribution_stateful_returns import (
    LotusPerformanceReturnsClientProtocol,
    StatefulReturnsContext,
    build_stateful_returns_request,
    fetch_stateful_returns_context,
    requires_active_attribution,
)
from app.services.benchmark_exposure_history import (
    BenchmarkExposureHistoryRequest,
    fetch_benchmark_exposure_history,
)
from app.upstream_errors import missing_upstream_data


__all__ = [
    "LotusCoreClientProtocol",
    "LotusPerformanceClientProtocol",
    "ResolvedStatefulAttributionInputs",
    "StatefulReturnsContext",
    "build_stateful_returns_request",
    "build_stateful_stateless_input",
    "resolve_stateful_attribution_inputs",
]


class LotusPerformanceClientProtocol(LotusPerformanceReturnsClientProtocol, Protocol):
    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


class LotusCoreClientProtocol(Protocol):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ResolvedStatefulAttributionInputs:
    stateless_input: HistoricalAttributionStatelessInput
    returns_request: dict[str, Any]


@dataclass(frozen=True)
class _StatefulExposureHistories:
    exposure_history: list[ExposurePoint]
    benchmark_exposure_history: list[ExposurePoint]


def _validate_benchmark_exposure_alignment(
    *,
    benchmark_returns: list[ReturnPoint],
    benchmark_exposure_history: list[ExposurePoint],
) -> None:
    return_dates = {point.date for point in benchmark_returns}
    exposure_dates = {point.date for point in benchmark_exposure_history}
    missing_dates = sorted(return_dates - exposure_dates)
    if missing_dates:
        sample = ", ".join(date_value.isoformat() for date_value in missing_dates[:5])
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message=(
                "lotus-performance benchmark exposure context missing rows for benchmark "
                f"return dates: {sample}"
            ),
        )


def validate_stateful_groupings(grouping_dimensions: list[GroupingDimension]) -> None:
    if "CUSTOM" in grouping_dimensions:
        raise ValueError(
            "stateful historical-attribution does not support grouping_dimension=CUSTOM"
        )


async def _fetch_active_benchmark_exposure_history(
    *,
    stateful: HistoricalAttributionStatefulInput,
    performance_client: LotusPerformanceClientProtocol,
    benchmark_returns: list[ReturnPoint],
    start_date: date,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[ExposurePoint]:
    benchmark_exposure_history = await fetch_benchmark_exposure_history(
        BenchmarkExposureHistoryRequest(
            performance_client=performance_client,
            portfolio_id=stateful.portfolio_id,
            as_of_date=stateful.as_of_date,
            start_date=start_date,
            reporting_currency=stateful.reporting_currency,
            grouping_dimensions=grouping_dimensions,
            correlation_id=correlation_id,
        )
    )
    _validate_benchmark_exposure_alignment(
        benchmark_returns=benchmark_returns,
        benchmark_exposure_history=benchmark_exposure_history,
    )
    return benchmark_exposure_history


def build_stateful_stateless_input(
    *,
    stateful: HistoricalAttributionStatefulInput,
    returns_context: StatefulReturnsContext,
    exposure_history: list[ExposurePoint],
    benchmark_exposure_history: list[ExposurePoint],
) -> HistoricalAttributionStatelessInput:
    return HistoricalAttributionStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=returns_context.portfolio_returns,
        benchmark_returns=returns_context.benchmark_returns,
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
        attribution_options=stateful.attribution_options,
    )


async def _stateful_exposure_histories(
    *,
    stateful: HistoricalAttributionStatefulInput,
    core_client: LotusCoreClientProtocol,
    performance_client: LotusPerformanceClientProtocol,
    returns_context: StatefulReturnsContext,
    grouping_dimensions: list[GroupingDimension],
    requires_active: bool,
    correlation_id: str | None,
) -> _StatefulExposureHistories:
    exposure_history = await fetch_stateful_exposure_history(
        stateful=stateful,
        core_client=core_client,
        start_date=returns_context.start_date,
        grouping_dimensions=grouping_dimensions,
        correlation_id=correlation_id,
    )
    benchmark_exposure_history = (
        await _fetch_active_benchmark_exposure_history(
            stateful=stateful,
            performance_client=performance_client,
            benchmark_returns=returns_context.benchmark_returns,
            start_date=returns_context.start_date,
            grouping_dimensions=grouping_dimensions,
            correlation_id=correlation_id,
        )
        if requires_active
        else []
    )
    return _StatefulExposureHistories(
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
    )


async def resolve_stateful_attribution_inputs(
    stateful: HistoricalAttributionStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> ResolvedStatefulAttributionInputs:
    options = stateful.attribution_options
    requested_groupings = options.grouping_dimensions
    validate_stateful_groupings(requested_groupings)

    requires_active = requires_active_attribution(stateful)
    returns_context = await fetch_stateful_returns_context(
        stateful=stateful,
        performance_client=performance_client,
        correlation_id=correlation_id,
    )
    exposure_histories = await _stateful_exposure_histories(
        stateful=stateful,
        core_client=core_client,
        performance_client=performance_client,
        returns_context=returns_context,
        grouping_dimensions=requested_groupings,
        requires_active=requires_active,
        correlation_id=correlation_id,
    )
    return ResolvedStatefulAttributionInputs(
        stateless_input=build_stateful_stateless_input(
            stateful=stateful,
            returns_context=returns_context,
            exposure_history=exposure_histories.exposure_history,
            benchmark_exposure_history=exposure_histories.benchmark_exposure_history,
        ),
        returns_request=returns_context.returns_request,
    )
