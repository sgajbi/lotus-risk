from __future__ import annotations

from typing import Any

import httpx

from app.integrations._downstream_client_profile import resolve_downstream_client_profile
from app.integrations.lotus_core_operations import (
    execute_add_simulation_changes_request,
    execute_core_snapshot_request,
    execute_create_simulation_session_request,
    execute_instrument_enrichment_request,
    execute_position_analytics_timeseries_request,
    execute_risk_free_coverage_request,
    execute_risk_free_series_request,
)
from app.integrations.lotus_core_transport import (
    DEFAULT_LOTUS_CORE_BASE_URL as _DEFAULT_LOTUS_CORE_BASE_URL,
    resolve_lotus_core_base_url,
)

DEFAULT_LOTUS_CORE_BASE_URL = _DEFAULT_LOTUS_CORE_BASE_URL


class LotusCoreClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = resolve_lotus_core_base_url(base_url)
        self._profile = resolve_downstream_client_profile(
            env_prefix="LOTUS_CORE",
            default_timeout_seconds=timeout_seconds or 10.0,
        )
        self._http_client = http_client

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
        return await execute_create_simulation_session_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            portfolio_id=portfolio_id,
            ttl_hours=ttl_hours,
            created_by=created_by,
            correlation_id=correlation_id,
        )

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        correlation_id: str | None,
        idempotency_key: str,
        change_set_fingerprint: str,
    ) -> dict[str, Any]:
        return await execute_add_simulation_changes_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            session_id=session_id,
            changes=changes,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            change_set_fingerprint=change_set_fingerprint,
        )

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await execute_core_snapshot_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            portfolio_id=portfolio_id,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await execute_instrument_enrichment_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            security_ids=security_ids,
            correlation_id=correlation_id,
        )

    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await execute_position_analytics_timeseries_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            portfolio_id=portfolio_id,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )

    async def get_risk_free_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await execute_risk_free_series_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )

    async def get_risk_free_coverage(
        self,
        *,
        currency: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await execute_risk_free_coverage_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            currency=currency,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )
