"""Shared async submit/poll execution against lotus-performance analytics workflows.

Returns-series and contribution share one producer async contract: a submit may answer
202 with ``{calculation_id, poll_path, result_path}``; the caller then polls the status
path (when supplied) and the result path with the same per-request authority headers as
the submit, so the polling identity is always the submitting tenant.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, NoReturn

import httpx

from app.integrations._downstream_client_profile import execute_downstream_request_json
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data


@dataclass(frozen=True)
class AsyncExecutionOperations:
    """Operation labels for one async workflow's submit, status, and result requests."""

    submit: str
    status: str
    result: str
    workflow_name: str


def async_accepted_paths(
    accepted_payload: dict[str, Any],
    *,
    operations: AsyncExecutionOperations,
) -> tuple[str, str | None]:
    result_path = accepted_payload.get("result_path")
    if not isinstance(result_path, str) or not result_path.startswith("/"):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=operations.submit,
            message="lotus-performance async accepted payload missing result_path",
        )

    poll_path = accepted_payload.get("poll_path")
    if poll_path is not None and (not isinstance(poll_path, str) or not poll_path.startswith("/")):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=operations.submit,
            message="lotus-performance async accepted payload has invalid poll_path",
        )
    return result_path, poll_path


def raise_async_failure(
    execution_payload: dict[str, Any],
    *,
    operations: AsyncExecutionOperations,
) -> NoReturn:
    error_message = execution_payload.get("error_message")
    detail = f": {error_message}" if isinstance(error_message, str) and error_message else ""
    raise missing_upstream_data(
        service="lotus-performance",
        operation=operations.submit,
        message=f"lotus-performance async {operations.workflow_name} failed{detail}",
    )


def raise_async_poll_timeout(
    last_status: str,
    *,
    operations: AsyncExecutionOperations,
) -> NoReturn:
    raise missing_upstream_data(
        service="lotus-performance",
        operation=operations.submit,
        message=(
            f"lotus-performance async {operations.workflow_name} did not complete within "
            f"polling budget (last_status={last_status})"
        ),
    )


def required_async_result(
    result_payload: dict[str, Any] | None,
    *,
    operations: AsyncExecutionOperations,
) -> dict[str, Any]:
    if result_payload is not None:
        return result_payload
    raise missing_upstream_data(
        service="lotus-performance",
        operation=operations.submit,
        message=f"lotus-performance async {operations.workflow_name} result returned no payload",
    )


def parse_dict_payload(
    response: httpx.Response,
    *,
    invalid_message: str,
    operation: str,
) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=operation,
            message=invalid_message,
        )
    return payload


def _parse_optional_dict_payload(
    response: httpx.Response,
    *,
    invalid_message: str,
    operation: str,
) -> dict[str, Any] | None:
    payload = response.json()
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=operation,
            message=invalid_message,
        )
    return payload


async def poll_async_result(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    accepted_payload: dict[str, Any],
    headers: dict[str, str],
    started_at: float,
    async_max_polls: int,
    async_poll_interval_seconds: float,
    operations: AsyncExecutionOperations,
) -> dict[str, Any]:
    result_path, poll_path = async_accepted_paths(accepted_payload, operations=operations)
    last_status = "pending"
    for _ in range(async_max_polls):
        result_payload, last_status = await _poll_once(
            client=client,
            base_url=base_url,
            result_path=result_path,
            poll_path=poll_path,
            headers=headers,
            started_at=started_at,
            last_status=last_status,
            operations=operations,
        )
        if result_payload is not None:
            return result_payload

        await asyncio.sleep(async_poll_interval_seconds)

    raise_async_poll_timeout(last_status, operations=operations)


async def _poll_once(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    result_path: str,
    poll_path: str | None,
    headers: dict[str, str],
    started_at: float,
    last_status: str,
    operations: AsyncExecutionOperations,
) -> tuple[dict[str, Any] | None, str]:
    next_status = last_status
    if poll_path:
        next_status = await _poll_status(
            client=client,
            base_url=base_url,
            poll_path=poll_path,
            headers=headers,
            started_at=started_at,
            last_status=last_status,
            operations=operations,
        )
    result_status, result_payload = await _get_result(
        client=client,
        base_url=base_url,
        result_path=result_path,
        headers=headers,
        started_at=started_at,
        operations=operations,
    )
    if result_status != 200:
        return None, next_status
    return required_async_result(result_payload, operations=operations), next_status


async def _poll_status(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    poll_path: str,
    headers: dict[str, str],
    started_at: float,
    last_status: str,
    operations: AsyncExecutionOperations,
) -> str:
    execution_payload = await execute_downstream_request_json(
        dependency="lotus-performance",
        operation=operations.status,
        started_at=started_at,
        request_factory=lambda: client.get(f"{base_url}{poll_path}", headers=headers),
        parse_response=lambda response: parse_dict_payload(
            response,
            invalid_message=(f"lotus-performance returned invalid JSON payload for {poll_path}"),
            operation=operations.status,
        ),
        record_success=False,
    )
    status = execution_payload.get("status")
    next_status = status if isinstance(status, str) else last_status
    if status == "failed":
        raise_async_failure(execution_payload, operations=operations)
    return next_status


async def _get_result(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    result_path: str,
    headers: dict[str, str],
    started_at: float,
    operations: AsyncExecutionOperations,
) -> tuple[int, dict[str, Any] | None]:
    return await execute_downstream_request_json(
        dependency="lotus-performance",
        operation=operations.result,
        started_at=started_at,
        request_factory=lambda: client.get(f"{base_url}{result_path}", headers=headers),
        accepted_status_codes={202, 404},
        parse_response=lambda response: (
            response.status_code,
            None
            if response.status_code in {202, 404}
            else _parse_optional_dict_payload(
                response,
                invalid_message="lotus-performance returned invalid async result payload",
                operation=operations.result,
            ),
        ),
        record_success=False,
    )


__all__ = [
    "AsyncExecutionOperations",
    "async_accepted_paths",
    "parse_dict_payload",
    "poll_async_result",
    "raise_async_failure",
    "raise_async_poll_timeout",
    "required_async_result",
]
