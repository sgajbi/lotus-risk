from __future__ import annotations

import os
from typing import Any

from app.integrations._downstream_client_profile import (
    DownstreamClientProfile,
    execute_downstream_request_json,
)
from app.integrations.performance_returns_series_async import (
    RETURNS_SERIES_OPERATION,
    ensure_dict_payload,
    poll_returns_series_result,
)
from app.observability import observation_start, record_upstream_request

DEFAULT_LOTUS_PERFORMANCE_BASE_URL = "http://performance.dev.lotus"
BENCHMARK_EXPOSURE_CONTEXT_OPERATION = "/integration/benchmarks/exposure-context"


def resolve_lotus_performance_base_url(base_url: str | None) -> str:
    configured_base_url = base_url or os.getenv("LOTUS_PERFORMANCE_BASE_URL")
    if not configured_base_url:
        configured_base_url = DEFAULT_LOTUS_PERFORMANCE_BASE_URL
    return configured_base_url.rstrip("/")


def correlation_headers(correlation_id: str | None) -> dict[str, str]:
    return {"X-Correlation-Id": correlation_id} if correlation_id else {}


async def execute_returns_series_request(
    *,
    profile: DownstreamClientProfile,
    base_url: str,
    request_payload: dict[str, Any],
    correlation_id: str | None,
    async_max_polls: int,
    async_poll_interval_seconds: float,
) -> dict[str, Any]:
    headers = correlation_headers(correlation_id)
    url = f"{base_url}{RETURNS_SERIES_OPERATION}"
    started_at = observation_start()
    async with profile.make_client() as client:
        status_code, payload = await _execute_initial_returns_series_request(
            client=client,
            url=url,
            request_payload=request_payload,
            headers=headers,
            started_at=started_at,
        )
        return await _finalize_returns_series_payload(
            client=client,
            base_url=base_url,
            status_code=status_code,
            payload=payload,
            headers=headers,
            started_at=started_at,
            async_max_polls=async_max_polls,
            async_poll_interval_seconds=async_poll_interval_seconds,
        )


async def _execute_initial_returns_series_request(
    *,
    client: Any,
    url: str,
    request_payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
) -> tuple[int, dict[str, Any]]:
    return await execute_downstream_request_json(
        dependency="lotus-performance",
        operation=RETURNS_SERIES_OPERATION,
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


async def execute_benchmark_exposure_context_request(
    *,
    profile: DownstreamClientProfile,
    base_url: str,
    request_payload: dict[str, Any],
    correlation_id: str | None,
) -> dict[str, Any]:
    headers = correlation_headers(correlation_id)
    url = f"{base_url}{BENCHMARK_EXPOSURE_CONTEXT_OPERATION}"
    started_at = observation_start()
    async with profile.make_client() as client:
        return await execute_downstream_request_json(
            dependency="lotus-performance",
            operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
            started_at=started_at,
            request_factory=lambda: client.post(url, json=request_payload, headers=headers),
            parse_response=lambda response: ensure_dict_payload(
                response,
                invalid_message=(
                    "lotus-performance returned invalid benchmark exposure context payload"
                ),
            ),
        )


async def _finalize_returns_series_payload(
    *,
    client: Any,
    base_url: str,
    status_code: int,
    payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
    async_max_polls: int,
    async_poll_interval_seconds: float,
) -> dict[str, Any]:
    if status_code == 202:
        payload = await poll_returns_series_result(
            client=client,
            base_url=base_url,
            accepted_payload=payload,
            headers=headers,
            started_at=started_at,
            async_max_polls=async_max_polls,
            async_poll_interval_seconds=async_poll_interval_seconds,
        )
    record_upstream_request(
        dependency="lotus-performance",
        operation=RETURNS_SERIES_OPERATION,
        outcome="success",
        category="ok",
        started_at=started_at,
    )
    return payload


__all__ = [
    "DEFAULT_LOTUS_PERFORMANCE_BASE_URL",
    "correlation_headers",
    "execute_benchmark_exposure_context_request",
    "execute_returns_series_request",
    "resolve_lotus_performance_base_url",
]
