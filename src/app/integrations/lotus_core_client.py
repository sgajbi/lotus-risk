from __future__ import annotations

import os
from typing import Any

import httpx


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
            configured_base_url = "http://localhost:8000"
        resolved_base_url = configured_base_url.rstrip("/")
        resolved_timeout = timeout_seconds or float(os.getenv("LOTUS_CORE_TIMEOUT_SECONDS", "10"))
        self._base_url = resolved_base_url
        self._timeout = httpx.Timeout(resolved_timeout)

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
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError(f"lotus-core returned invalid JSON payload for {path}")
                return data
        except httpx.HTTPStatusError as exc:
            detail = self._extract_error_detail(exc.response)
            raise ValueError(
                f"lotus-core {path} failed ({exc.response.status_code}): {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ValueError(f"lotus-core {path} unavailable: {exc}") from exc

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or "unknown error"
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, dict):
                message = detail.get("message")
                if isinstance(message, str):
                    return message
        return str(payload)
