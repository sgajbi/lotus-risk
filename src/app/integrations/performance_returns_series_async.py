from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.integrations._downstream_client_profile import execute_downstream_request_json
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data

RETURNS_SERIES_OPERATION = "/integration/returns/series"


def ensure_dict_payload(
    response: httpx.Response,
    *,
    invalid_message: str,
) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=response.request.url.path,
            message=invalid_message,
        )
    return payload


def _parse_async_result_payload(
    response: httpx.Response,
    *,
    invalid_message: str,
) -> dict[str, Any] | None:
    payload = response.json()
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=response.request.url.path,
            message=invalid_message,
        )
    return payload


def _async_returns_series_paths(accepted_payload: dict[str, Any]) -> tuple[str, str | None]:
    result_path = accepted_payload.get("result_path")
    if not isinstance(result_path, str) or not result_path.startswith("/"):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=RETURNS_SERIES_OPERATION,
            message="lotus-performance async accepted payload missing result_path",
        )

    poll_path = accepted_payload.get("poll_path")
    if poll_path is not None and (not isinstance(poll_path, str) or not poll_path.startswith("/")):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=RETURNS_SERIES_OPERATION,
            message="lotus-performance async accepted payload has invalid poll_path",
        )
    return result_path, poll_path


def _raise_returns_series_async_failure(execution_payload: dict[str, Any]) -> None:
    error_message = execution_payload.get("error_message")
    if isinstance(error_message, str) and error_message:
        raise missing_upstream_data(
            service="lotus-performance",
            operation=RETURNS_SERIES_OPERATION,
            message=f"lotus-performance async returns-series failed: {error_message}",
        )
    raise missing_upstream_data(
        service="lotus-performance",
        operation=RETURNS_SERIES_OPERATION,
        message="lotus-performance async returns-series failed",
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
    result_path, poll_path = _async_returns_series_paths(accepted_payload)
    last_status = "pending"
    for _ in range(async_max_polls):
        if poll_path:
            last_status = await _poll_returns_series_status(
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
        if result_status == 200:
            if result_payload is None:
                raise missing_upstream_data(
                    service="lotus-performance",
                    operation=RETURNS_SERIES_OPERATION,
                    message="lotus-performance async returns-series result returned no payload",
                )
            return result_payload

        await asyncio.sleep(async_poll_interval_seconds)

    raise missing_upstream_data(
        service="lotus-performance",
        operation=RETURNS_SERIES_OPERATION,
        message=(
            "lotus-performance async returns-series did not complete within polling budget "
            f"(last_status={last_status})"
        ),
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
        _raise_returns_series_async_failure(execution_payload)
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
        parse_response=lambda response: (
            response.status_code,
            None
            if response.status_code in {202, 404}
            else _parse_async_result_payload(
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
