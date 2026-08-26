from __future__ import annotations

from typing import Any

from app.contracts.attribution import (
    AttributionInputMode,
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionResponse,
    HistoricalAttributionStatefulInput,
    HistoricalAttributionStatelessInput,
)
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_exposure_history import (
    as_decimal,
    build_exposure_points,
    build_issuer_map,
    group_key_and_label,
)
from app.services.attribution_stateful_inputs import (
    LotusCoreClientProtocol,
    LotusPerformanceClientProtocol,
    StatefulReturnsContext,
    build_stateful_returns_request,
    build_stateful_stateless_input,
    resolve_stateful_attribution_inputs,
)
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint


def _build_stateful_returns_request(stateful: HistoricalAttributionStatefulInput) -> dict[str, Any]:
    return build_stateful_returns_request(stateful)


def _group_key_and_label(
    *,
    row: dict[str, Any],
    grouping_dimension: GroupingDimension,
    issuer_map: dict[str, tuple[str, str | None]],
) -> tuple[str, str | None]:
    return group_key_and_label(
        row=row,
        grouping_dimension=grouping_dimension,
        issuer_map=issuer_map,
    )


def _as_decimal(value: Any) -> object:
    return as_decimal(value)


def _build_exposure_points(
    *,
    rows: list[dict[str, Any]],
    grouping_dimensions: list[GroupingDimension],
    issuer_map: dict[str, tuple[str, str | None]],
) -> list[ExposurePoint]:
    return build_exposure_points(
        rows=rows,
        grouping_dimensions=grouping_dimensions,
        issuer_map=issuer_map,
    )


async def _build_issuer_map(
    *,
    core_client: LotusCoreClientProtocol,
    rows: list[dict[str, Any]],
    correlation_id: str | None,
) -> dict[str, tuple[str, str | None]]:
    return await build_issuer_map(
        core_client=core_client,
        rows=rows,
        correlation_id=correlation_id,
    )


def _build_stateful_stateless_input(
    *,
    stateful: HistoricalAttributionStatefulInput,
    returns_context: StatefulReturnsContext,
    exposure_history: list[ExposurePoint],
    benchmark_exposure_history: list[ExposurePoint],
) -> HistoricalAttributionStatelessInput:
    return build_stateful_stateless_input(
        stateful=stateful,
        returns_context=returns_context,
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
    )


def _attach_stateful_lineage(
    *,
    response: HistoricalAttributionResponse,
    returns_request: dict[str, Any],
) -> HistoricalAttributionResponse:
    response.metadata.source_services = ordered_source_services(
        "lotus-performance",
        "lotus-core",
    )
    response.metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=returns_request,
    )
    return response


async def calculate_historical_attribution_stateful(
    stateful: HistoricalAttributionStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> HistoricalAttributionResponse:
    resolved_inputs = await resolve_stateful_attribution_inputs(
        stateful,
        performance_client=performance_client,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    response = calculate_historical_attribution(
        resolved_inputs.stateless_input,
        input_mode=AttributionInputMode.STATEFUL,
    )
    return _attach_stateful_lineage(
        response=response,
        returns_request=resolved_inputs.returns_request,
    )
