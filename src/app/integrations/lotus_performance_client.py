from __future__ import annotations

from typing import Any

import httpx

from app.integrations._downstream_client_profile import resolve_downstream_client_profile
from app.integrations.downstream_profile_env import env_float_with_default, env_int_with_default
from app.integrations.lotus_performance_transport import (
    DEFAULT_LOTUS_PERFORMANCE_BASE_URL as _DEFAULT_LOTUS_PERFORMANCE_BASE_URL,
    execute_benchmark_exposure_context_request,
    execute_returns_series_request,
    resolve_lotus_performance_base_url,
)

DEFAULT_LOTUS_PERFORMANCE_BASE_URL = _DEFAULT_LOTUS_PERFORMANCE_BASE_URL


class LotusPerformanceClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = resolve_lotus_performance_base_url(base_url)
        self._profile = resolve_downstream_client_profile(
            env_prefix="LOTUS_PERFORMANCE",
            default_timeout_seconds=timeout_seconds or 10.0,
        )
        self._http_client = http_client
        self._async_poll_interval_seconds = env_float_with_default(
            "LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS", 1.0
        )
        self._async_max_polls = env_int_with_default("LOTUS_PERFORMANCE_ASYNC_MAX_POLLS", 60)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await execute_returns_series_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            request_payload=request_payload,
            correlation_id=correlation_id,
            async_max_polls=self._async_max_polls,
            async_poll_interval_seconds=self._async_poll_interval_seconds,
        )

    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return await execute_benchmark_exposure_context_request(
            profile=self._profile,
            client=self._http_client,
            base_url=self._base_url,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )
