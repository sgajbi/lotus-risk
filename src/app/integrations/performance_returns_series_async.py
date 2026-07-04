from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.integrations._downstream_client_profile import execute_downstream_request_json
from app.integrations.performance_returns_payloads import (
    RETURNS_SERIES_OPERATION,
    async_returns_series_paths,
    ensure_dict_payload,
    parse_async_result_payload,
    raise_returns_series_async_failure,
    raise_returns_series_poll_timeout,
    required_async_result_payload,
)

__all__ = ["RETURNS_SERIES_OPERATION", "ensure_dict_payload", "poll_returns_series_result"]


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
    result_path, poll_path = async_returns_series_paths(accepted_payload)
    last_status = "pending"
    for _ in range(async_max_polls):
        result_payload, last_status = await _poll_returns_series_once(
            client=client,
            base_url=base_url,
            result_path=result_path,
            poll_path=poll_path,
            headers=headers,
            started_at=started_at,
            last_status=last_status,
        )
        if result_payload is not None:
            return result_payload

        await asyncio.sleep(async_poll_interval_seconds)

    raise_returns_series_poll_timeout(last_status)


async def _poll_returns_series_once(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    result_path: str,
    poll_path: str | None,
    headers: dict[str, str],
    started_at: float,
    last_status: str,
) -> tuple[dict[str, Any] | None, str]:
    next_status = await _returns_series_poll_status_if_configured(
        client=client,
        base_url=base_url,
        poll_path=poll_path,
        headers=headers,
        started_at=started_at,
        last_status=last_status,
    )
    result_status, result_payload = await _get_returns_series_result(
        client=client,
        base_url=base_url,
        result_path=result_path,
        headers=headers,
        started_at=started_at,
    )
    if result_status != 200:
        return None, next_status
    return required_async_result_payload(result_payload), next_status


async def _returns_series_poll_status_if_configured(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    poll_path: str | None,
    headers: dict[str, str],
    started_at: float,
    last_status: str,
) -> str:
    if not poll_path:
        return last_status
    return await _poll_returns_series_status(
        client=client,
        base_url=base_url,
        poll_path=poll_path,
        headers=headers,
        started_at=started_at,
        last_status=last_status,
    )


async def _poll_returns_series_status(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    poll_path: str,
    headers: dict[str, str],
    started_at: float,
    last_status: str,
) -> str:
    execution_payload = await _get_dict(
        client=client,
        base_url=base_url,
        path=poll_path,
        headers=headers,
        operation=poll_path,
        started_at=started_at,
        record_success=False,
    )
    status = execution_payload.get("status")
    next_status = status if isinstance(status, str) else last_status
    if status == "failed":
        raise_returns_series_async_failure(execution_payload)
    return next_status


async def _get_returns_series_result(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    result_path: str,
    headers: dict[str, str],
    started_at: float,
) -> tuple[int, dict[str, Any] | None]:
    return await execute_downstream_request_json(
        dependency="lotus-performance",
        operation=result_path,
        started_at=started_at,
        request_factory=lambda: client.get(f"{base_url}{result_path}", headers=headers),
        accepted_status_codes={202, 404},
        parse_response=lambda response: (
            response.status_code,
            None
            if response.status_code in {202, 404}
            else parse_async_result_payload(
                response,
                invalid_message="lotus-performance returned invalid async result payload",
            ),
        ),
        record_success=False,
    )


async def _get_dict(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    path: str,
    headers: dict[str, str],
    operation: str,
    started_at: float,
    record_success: bool = True,
) -> dict[str, Any]:
    return await execute_downstream_request_json(
        dependency="lotus-performance",
        operation=operation,
        started_at=started_at,
        request_factory=lambda: client.get(f"{base_url}{path}", headers=headers),
        parse_response=lambda response: ensure_dict_payload(
            response,
            invalid_message=f"lotus-performance returned invalid JSON payload for {path}",
        ),
        record_success=record_success,
    )
