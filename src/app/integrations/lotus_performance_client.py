from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from app.integrations._downstream_client_profile import (
    _env_float_with_default,
    _env_int_with_default,
    execute_downstream_request_json,
    resolve_downstream_client_profile,
)
from app.observability import observation_start, record_upstream_request
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data

DEFAULT_LOTUS_PERFORMANCE_BASE_URL = "http://performance.dev.lotus"
RETURNS_SERIES_OPERATION = "/integration/returns/series"


def _correlation_headers(correlation_id: str | None) -> dict[str, str]:
    return {"X-Correlation-Id": correlation_id} if correlation_id else {}


def _ensure_dict_payload(
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


async def _poll_returns_series_result(
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
        parse_response=lambda response: _ensure_dict_payload(
            response,
            invalid_message=f"lotus-performance returned invalid JSON payload for {path}",
        ),
        record_success=record_success,
    )


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
                    _ensure_dict_payload(
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
                parse_response=lambda response: _ensure_dict_payload(
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
            payload = await _poll_returns_series_result(
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
