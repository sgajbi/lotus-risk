from __future__ import annotations

from typing import Any

import httpx

from app.integrations.performance_async_execution import (
    AsyncExecutionOperations,
    poll_async_result,
)
from app.integrations.performance_returns_payloads import (
    RETURNS_SERIES_OPERATION,
    ensure_dict_payload,
)
from app.integrations.upstream_operations import (
    LOTUS_PERFORMANCE_RETURNS_SERIES_RESULT_OPERATION,
    LOTUS_PERFORMANCE_RETURNS_SERIES_STATUS_OPERATION,
)

__all__ = ["RETURNS_SERIES_OPERATION", "ensure_dict_payload", "poll_returns_series_result"]

RETURNS_SERIES_ASYNC_OPERATIONS = AsyncExecutionOperations(
    submit=RETURNS_SERIES_OPERATION,
    status=LOTUS_PERFORMANCE_RETURNS_SERIES_STATUS_OPERATION,
    result=LOTUS_PERFORMANCE_RETURNS_SERIES_RESULT_OPERATION,
    workflow_name="returns-series",
)


async def poll_returns_series_result(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    accepted_payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
    async_max_polls: int,
    async_poll_interval_seconds: float,
) -> dict[str, Any]:
    return await poll_async_result(
        client=client,
        base_url=base_url,
        accepted_payload=accepted_payload,
        headers=headers,
        started_at=started_at,
        async_max_polls=async_max_polls,
        async_poll_interval_seconds=async_poll_interval_seconds,
        operations=RETURNS_SERIES_ASYNC_OPERATIONS,
    )
