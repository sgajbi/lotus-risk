from __future__ import annotations

import os
from typing import Any

import httpx

from app.integrations._downstream_client_profile import (
    _env_float_with_default,
    _env_int_with_default,
    execute_downstream_request_json,
    resolve_downstream_client_profile,
)
from app.integrations.performance_returns_series_async import (
    RETURNS_SERIES_OPERATION,
    ensure_dict_payload,
    poll_returns_series_result,
)
from app.observability import observation_start, record_upstream_request

DEFAULT_LOTUS_PERFORMANCE_BASE_URL = "http://performance.dev.lotus"


def _correlation_headers(correlation_id: str | None) -> dict[str, str]:
    return {"X-Correlation-Id": correlation_id} if correlation_id else {}


class LotusPerformanceClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        configured_base_url = base_url or os.getenv("LOTUS_PERFORMANCE_BASE_URL")
        if not configured_base_url:
            configured_base_url = DEFAULT_LOTUS_PERFORMANCE_BASE_URL
        self._base_url = configured_base_url.rstrip("/")
        self._profile = resolve_downstream_client_profile(
            env_prefix="LOTUS_PERFORMANCE",
            default_timeout_seconds=timeout_seconds or 10.0,
        )
        self._async_poll_interval_seconds = _env_float_with_default(
            "LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS", 1.0
        )
        self._async_max_polls = _env_int_with_default("LOTUS_PERFORMANCE_ASYNC_MAX_POLLS", 60)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        headers = _correlation_headers(correlation_id)
        path = RETURNS_SERIES_OPERATION
        url = f"{self._base_url}{path}"
        started_at = observation_start()
        async with self._profile.make_client() as client:
            status_code, payload = await execute_downstream_request_json(
                dependency="lotus-performance",
                operation=path,
                started_at=started_at,
                request_factory=lambda: client.post(url, json=request_payload, headers=headers),
                parse_response=lambda response: (
                    response.status_code,
                    ensure_dict_payload(
                        response,
                        invalid_message=(
                            "lotus-performance returned invalid async accepted payload"
                            if response.status_code == 202
                            else "lotus-performance returned invalid JSON payload"
                        ),
                    ),
                ),
                record_success=False,
            )
            return await self._finalize_returns_series_payload(
                client=client,
                status_code=status_code,
                payload=payload,
                headers=headers,
                started_at=started_at,
            )

    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        headers = _correlation_headers(correlation_id)
        path = "/integration/benchmarks/exposure-context"
        url = f"{self._base_url}{path}"
        started_at = observation_start()
        async with self._profile.make_client() as client:
            return await execute_downstream_request_json(
                dependency="lotus-performance",
                operation=path,
                started_at=started_at,
                request_factory=lambda: client.post(url, json=request_payload, headers=headers),
                parse_response=lambda response: ensure_dict_payload(
                    response,
                    invalid_message="lotus-performance returned invalid benchmark exposure context payload",
                ),
            )

    async def _finalize_returns_series_payload(
        self,
        *,
        client: httpx.AsyncClient,
        status_code: int,
        payload: dict[str, Any],
        headers: dict[str, str],
        started_at: float,
    ) -> dict[str, Any]:
        if status_code == 202:
            payload = await poll_returns_series_result(
                client=client,
                base_url=self._base_url,
                accepted_payload=payload,
                headers=headers,
                started_at=started_at,
                async_max_polls=self._async_max_polls,
                async_poll_interval_seconds=self._async_poll_interval_seconds,
            )
        record_upstream_request(
            dependency="lotus-performance",
            operation=RETURNS_SERIES_OPERATION,
            outcome="success",
            category="ok",
            started_at=started_at,
        )
        return payload
