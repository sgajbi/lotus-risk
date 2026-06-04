from __future__ import annotations

import os
from typing import Any

import httpx

from app.integrations._downstream_client_profile import resolve_downstream_client_profile
from app.integrations._downstream_client_profile import execute_downstream_request_json
from app.observability import observation_start
from app.upstream_errors import (
    invalid_upstream_payload,
)

DEFAULT_LOTUS_CORE_BASE_URL = "http://core-control.dev.lotus"


def _parse_json_dict_payload(
    response: httpx.Response,
    *,
    invalid_message: str,
) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation=response.request.url.path,
            message=invalid_message,
        )
    return payload


class LotusCoreClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        configured_base_url = base_url
        if configured_base_url is None:
            configured_base_url = os.getenv("LOTUS_CORE_BASE_URL")
        if not configured_base_url:
            configured_base_url = DEFAULT_LOTUS_CORE_BASE_URL
        resolved_base_url = configured_base_url.rstrip("/")
        self._base_url = resolved_base_url
        self._profile = resolve_downstream_client_profile(
            env_prefix="LOTUS_CORE",
            default_timeout_seconds=timeout_seconds or 10.0,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"portfolio_id": portfolio_id}
        if ttl_hours is not None:
            payload["ttl_hours"] = ttl_hours
        if created_by:
            payload["created_by"] = created_by
        return await self._request_json(
            "POST",
            "/simulation-sessions",
            json_payload=payload,
            correlation_id=correlation_id,
        )

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/simulation-sessions/{session_id}/changes",
            json_payload={"changes": changes},
            correlation_id=correlation_id,
        )

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/integration/portfolios/{portfolio_id}/core-snapshot",
            json_payload=request_payload,
            correlation_id=correlation_id,
        )

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        payload = {"security_ids": security_ids}
        return await self._request_json(
            "POST",
            "/integration/instruments/enrichment-bulk",
            json_payload=payload,
            correlation_id=correlation_id,
        )

    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/integration/portfolios/{portfolio_id}/analytics/position-timeseries",
            json_payload=request_payload,
            correlation_id=correlation_id,
        )

    async def get_risk_free_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/integration/reference/risk-free-series",
            json_payload=request_payload,
            correlation_id=correlation_id,
        )

    async def get_risk_free_coverage(
        self,
        *,
        currency: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/integration/reference/risk-free-series/coverage?currency={currency}",
            json_payload=request_payload,
            correlation_id=correlation_id,
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        url = f"{self._base_url}{path}"
        started_at = observation_start()
        async with self._profile.make_client() as client:
            return await execute_downstream_request_json(
                dependency="lotus-core",
                operation=path,
                started_at=started_at,
                request_factory=lambda: client.request(
                    method=method,
                    url=url,
                    json=json_payload,
                    headers=headers,
                ),
                parse_response=lambda response: _parse_json_dict_payload(
                    response=response,
                    invalid_message=f"lotus-core returned invalid JSON payload for {path}",
                ),
            )
