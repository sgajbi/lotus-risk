from __future__ import annotations

from typing import Any

from app.integrations._downstream_client_profile import resolve_downstream_client_profile
from app.integrations.lotus_core_transport import (
    DEFAULT_LOTUS_CORE_BASE_URL as _DEFAULT_LOTUS_CORE_BASE_URL,
    execute_lotus_core_json_request,
    resolve_lotus_core_base_url,
)

DEFAULT_LOTUS_CORE_BASE_URL = _DEFAULT_LOTUS_CORE_BASE_URL


class LotusCoreClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._base_url = resolve_lotus_core_base_url(base_url)
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
        return await execute_lotus_core_json_request(
            profile=self._profile,
            base_url=self._base_url,
            method=method,
            path=path,
            json_payload=json_payload,
            correlation_id=correlation_id,
        )
