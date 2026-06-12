from __future__ import annotations

from typing import Any

import httpx

from app.integrations._downstream_client_profile import DownstreamClientProfile
from app.integrations.lotus_core_transport import execute_lotus_core_json_request


def build_simulation_session_payload(
    *,
    portfolio_id: str,
    ttl_hours: int | None,
    created_by: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"portfolio_id": portfolio_id}
    if ttl_hours is not None:
        payload["ttl_hours"] = ttl_hours
    if created_by:
        payload["created_by"] = created_by
    return payload


async def execute_create_simulation_session_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    portfolio_id: str,
    ttl_hours: int | None,
    created_by: str | None,
    correlation_id: str | None,
) -> dict[str, Any]:
    return await execute_lotus_core_json_request(
        profile=profile,
        client=client,
        base_url=base_url,
        method="POST",
        path="/simulation-sessions",
        json_payload=build_simulation_session_payload(
            portfolio_id=portfolio_id,
            ttl_hours=ttl_hours,
            created_by=created_by,
        ),
        correlation_id=correlation_id,
    )


async def execute_add_simulation_changes_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    session_id: str,
    changes: list[dict[str, Any]],
    correlation_id: str | None,
) -> dict[str, Any]:
    return await execute_lotus_core_json_request(
        profile=profile,
        client=client,
        base_url=base_url,
        method="POST",
        path=f"/simulation-sessions/{session_id}/changes",
        json_payload={"changes": changes},
        correlation_id=correlation_id,
    )


async def execute_core_snapshot_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    portfolio_id: str,
    request_payload: dict[str, Any],
    correlation_id: str | None,
) -> dict[str, Any]:
    return await execute_lotus_core_json_request(
        profile=profile,
        client=client,
        base_url=base_url,
        method="POST",
        path=f"/integration/portfolios/{portfolio_id}/core-snapshot",
        json_payload=request_payload,
        correlation_id=correlation_id,
    )


async def execute_instrument_enrichment_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    security_ids: list[str],
    correlation_id: str | None,
) -> dict[str, Any]:
    return await execute_lotus_core_json_request(
        profile=profile,
        client=client,
        base_url=base_url,
        method="POST",
        path="/integration/instruments/enrichment-bulk",
        json_payload={"security_ids": security_ids},
        correlation_id=correlation_id,
    )


async def execute_position_analytics_timeseries_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    portfolio_id: str,
    request_payload: dict[str, Any],
    correlation_id: str | None,
) -> dict[str, Any]:
    return await execute_lotus_core_json_request(
        profile=profile,
        client=client,
        base_url=base_url,
        method="POST",
        path=f"/integration/portfolios/{portfolio_id}/analytics/position-timeseries",
        json_payload=request_payload,
        correlation_id=correlation_id,
    )


async def execute_risk_free_series_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    request_payload: dict[str, Any],
    correlation_id: str | None,
) -> dict[str, Any]:
    return await execute_lotus_core_json_request(
        profile=profile,
        client=client,
        base_url=base_url,
        method="POST",
        path="/integration/reference/risk-free-series",
        json_payload=request_payload,
        correlation_id=correlation_id,
    )


async def execute_risk_free_coverage_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    currency: str,
    request_payload: dict[str, Any],
    correlation_id: str | None,
) -> dict[str, Any]:
    return await execute_lotus_core_json_request(
        profile=profile,
        client=client,
        base_url=base_url,
        method="POST",
        path=f"/integration/reference/risk-free-series/coverage?currency={currency}",
        json_payload=request_payload,
        correlation_id=correlation_id,
    )


__all__ = [
    "build_simulation_session_payload",
    "execute_add_simulation_changes_request",
    "execute_core_snapshot_request",
    "execute_create_simulation_session_request",
    "execute_instrument_enrichment_request",
    "execute_position_analytics_timeseries_request",
    "execute_risk_free_coverage_request",
    "execute_risk_free_series_request",
]
