"""Fetch one admitted gross active group cut from the Performance producer."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol
from uuid import uuid4

from app.contracts.attribution import (
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionStatefulInput,
)
from app.contracts.downstream_authority import DownstreamAuthority
from app.contracts.risk import ReturnPoint
from app.services.attribution_active_group_evidence import (
    ActiveGroupEvidence,
    active_group_key_by_source_id,
    parse_active_group_evidence,
)


class ActiveGroupEvidenceClientProtocol(Protocol):
    async def get_group_return_evidence(
        self,
        *,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...


async def fetch_active_group_evidence(
    *,
    stateful: HistoricalAttributionStatefulInput,
    performance_client: ActiveGroupEvidenceClientProtocol,
    portfolio_returns: list[ReturnPoint],
    benchmark_returns: list[ReturnPoint],
    exposure_history: list[ExposurePoint],
    benchmark_exposure_history: list[ExposurePoint],
    benchmark_identity: tuple[str, str] | None,
    grouping_dimension: GroupingDimension,
    start_date: date,
    end_date: date,
    authority: DownstreamAuthority,
) -> tuple[ActiveGroupEvidence, dict[str, Any]]:
    """Return validated facts and the exact outgoing request for lineage."""
    if stateful.reporting_currency is None or stateful.net_or_gross != "GROSS":
        raise ValueError("v1 active group evidence requires gross basis and explicit currency")
    request_payload = {
        "calculation_id": str(uuid4()),
        "portfolio_id": stateful.portfolio_id,
        "as_of_date": stateful.as_of_date.isoformat(),
        "window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "grouping_dimension": grouping_dimension,
        "reporting_currency": stateful.reporting_currency,
    }
    response = await performance_client.get_group_return_evidence(
        request_payload=request_payload,
        authority=authority,
    )
    expected_source_ids = active_group_key_by_source_id(
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
        grouping_dimension=grouping_dimension,
        start_date=start_date,
        end_date=end_date,
    )
    evidence = parse_active_group_evidence(
        response,
        request=request_payload,
        expected_benchmark_id=(benchmark_identity[0] if benchmark_identity else None),
        grouping_dimension=grouping_dimension,
        expected_group_key_by_source_id=expected_source_ids,
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
    )
    return evidence, request_payload
