from __future__ import annotations

from typing import Any

import httpx

from app.contracts.downstream_authority import (
    DownstreamAuthority,
    downstream_authority_headers,
)
from app.integrations._downstream_client_profile import (
    DownstreamClientProfile,
    execute_downstream_request_json,
)
from app.integrations.downstream_base_url import resolve_downstream_base_url
from app.integrations.performance_async_execution import (
    AsyncExecutionOperations,
    parse_dict_payload,
    poll_async_result,
)
from app.integrations.performance_returns_series_async import (
    RETURNS_SERIES_ASYNC_OPERATIONS,
    ensure_dict_payload,
)
from app.integrations.upstream_operations import (
    LOTUS_PERFORMANCE_BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
    LOTUS_PERFORMANCE_CONTRIBUTION_OPERATION,
    LOTUS_PERFORMANCE_CONTRIBUTION_RESULT_OPERATION,
    LOTUS_PERFORMANCE_CONTRIBUTION_STATUS_OPERATION,
)
from app.observability import observation_start, record_upstream_request

DEFAULT_LOTUS_PERFORMANCE_BASE_URL = "http://performance.dev.lotus"
BENCHMARK_EXPOSURE_CONTEXT_OPERATION = LOTUS_PERFORMANCE_BENCHMARK_EXPOSURE_CONTEXT_OPERATION
CONTRIBUTION_OPERATION = LOTUS_PERFORMANCE_CONTRIBUTION_OPERATION

CONTRIBUTION_ASYNC_OPERATIONS = AsyncExecutionOperations(
    submit=LOTUS_PERFORMANCE_CONTRIBUTION_OPERATION,
    status=LOTUS_PERFORMANCE_CONTRIBUTION_STATUS_OPERATION,
    result=LOTUS_PERFORMANCE_CONTRIBUTION_RESULT_OPERATION,
    workflow_name="contribution",
)


def resolve_lotus_performance_base_url(base_url: str | None) -> str:
    return resolve_downstream_base_url(
        explicit_base_url=base_url,
        env_name="LOTUS_PERFORMANCE_BASE_URL",
        default_base_url=DEFAULT_LOTUS_PERFORMANCE_BASE_URL,
    )


async def execute_returns_series_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    request_payload: dict[str, Any],
    authority: DownstreamAuthority,
    async_max_polls: int,
    async_poll_interval_seconds: float,
) -> dict[str, Any]:
    return await _execute_async_workflow_request(
        profile=profile,
        client=client,
        base_url=base_url,
        request_payload=request_payload,
        authority=authority,
        async_max_polls=async_max_polls,
        async_poll_interval_seconds=async_poll_interval_seconds,
        operations=RETURNS_SERIES_ASYNC_OPERATIONS,
    )


async def execute_contribution_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    request_payload: dict[str, Any],
    authority: DownstreamAuthority,
    async_max_polls: int,
    async_poll_interval_seconds: float,
) -> dict[str, Any]:
    """Execute the tenant-owned contribution workflow that carries group-return evidence."""
    return await _execute_async_workflow_request(
        profile=profile,
        client=client,
        base_url=base_url,
        request_payload=request_payload,
        authority=authority,
        async_max_polls=async_max_polls,
        async_poll_interval_seconds=async_poll_interval_seconds,
        operations=CONTRIBUTION_ASYNC_OPERATIONS,
    )


async def _execute_async_workflow_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    request_payload: dict[str, Any],
    authority: DownstreamAuthority,
    async_max_polls: int,
    async_poll_interval_seconds: float,
    operations: AsyncExecutionOperations,
) -> dict[str, Any]:
    # Submit and every async status/result poll reuse these per-request authority headers,
    # so the polling identity is always the submitting tenant.
    headers = downstream_authority_headers(authority)
    url = f"{base_url}{operations.submit}"
    started_at = observation_start()
    if client is not None:
        return await _execute_async_workflow_with_client(
            client=client,
            base_url=base_url,
            url=url,
            request_payload=request_payload,
            headers=headers,
            started_at=started_at,
            async_max_polls=async_max_polls,
            async_poll_interval_seconds=async_poll_interval_seconds,
            operations=operations,
        )
    async with profile.make_client() as owned_client:
        return await _execute_async_workflow_with_client(
            client=owned_client,
            base_url=base_url,
            url=url,
            request_payload=request_payload,
            headers=headers,
            started_at=started_at,
            async_max_polls=async_max_polls,
            async_poll_interval_seconds=async_poll_interval_seconds,
            operations=operations,
        )


async def _execute_async_workflow_with_client(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    url: str,
    request_payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
    async_max_polls: int,
    async_poll_interval_seconds: float,
    operations: AsyncExecutionOperations,
) -> dict[str, Any]:
    status_code, payload = await execute_downstream_request_json(
        dependency="lotus-performance",
        operation=operations.submit,
        started_at=started_at,
        request_factory=lambda: client.post(url, json=request_payload, headers=headers),
        parse_response=lambda response: (
            response.status_code,
            parse_dict_payload(
                response,
                operation=operations.submit,
                invalid_message=(
                    "lotus-performance returned invalid async accepted payload"
                    if response.status_code == 202
                    else "lotus-performance returned invalid JSON payload"
                ),
            ),
        ),
        record_success=False,
    )
    if status_code == 202:
        payload = await poll_async_result(
            client=client,
            base_url=base_url,
            accepted_payload=payload,
            headers=headers,
            started_at=started_at,
            async_max_polls=async_max_polls,
            async_poll_interval_seconds=async_poll_interval_seconds,
            operations=operations,
        )
    record_upstream_request(
        dependency="lotus-performance",
        operation=operations.submit,
        outcome="success",
        category="ok",
        started_at=started_at,
    )
    return payload


async def execute_benchmark_exposure_context_request(
    *,
    profile: DownstreamClientProfile,
    client: httpx.AsyncClient | None,
    base_url: str,
    request_payload: dict[str, Any],
    authority: DownstreamAuthority,
) -> dict[str, Any]:
    headers = downstream_authority_headers(authority)
    url = f"{base_url}{BENCHMARK_EXPOSURE_CONTEXT_OPERATION}"
    started_at = observation_start()
    if client is not None:
        return await _execute_benchmark_exposure_context_request_with_client(
            client=client,
            url=url,
            request_payload=request_payload,
            headers=headers,
            started_at=started_at,
        )
    async with profile.make_client() as owned_client:
        return await _execute_benchmark_exposure_context_request_with_client(
            client=owned_client,
            url=url,
            request_payload=request_payload,
            headers=headers,
            started_at=started_at,
        )


async def _execute_benchmark_exposure_context_request_with_client(
    *,
    client: httpx.AsyncClient,
    url: str,
    request_payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
) -> dict[str, Any]:
    return await execute_downstream_request_json(
        dependency="lotus-performance",
        operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
        started_at=started_at,
        request_factory=lambda: client.post(url, json=request_payload, headers=headers),
        parse_response=lambda response: ensure_dict_payload(
            response,
            operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
            invalid_message="lotus-performance returned invalid benchmark exposure context payload",
        ),
    )


__all__ = [
    "CONTRIBUTION_ASYNC_OPERATIONS",
    "CONTRIBUTION_OPERATION",
    "DEFAULT_LOTUS_PERFORMANCE_BASE_URL",
    "execute_benchmark_exposure_context_request",
    "execute_contribution_request",
    "execute_returns_series_request",
    "resolve_lotus_performance_base_url",
]
