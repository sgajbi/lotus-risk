from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from app.observability import observation_start, record_upstream_request
from app.upstream_errors import (
    UpstreamServiceError,
    classify_upstream_http_error,
    classify_upstream_transport_error,
    extract_upstream_error_detail,
    invalid_upstream_payload,
    missing_upstream_data,
)

DEFAULT_LOTUS_PERFORMANCE_BASE_URL = "http://performance.dev.lotus"


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
        self._timeout = httpx.Timeout(
            timeout_seconds or float(os.getenv("LOTUS_PERFORMANCE_TIMEOUT_SECONDS", "10"))
        )
        self._async_poll_interval_seconds = float(
            os.getenv("LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS", "1")
        )
        self._async_max_polls = int(os.getenv("LOTUS_PERFORMANCE_ASYNC_MAX_POLLS", "60"))

    @property
    def base_url(self) -> str:
        return self._base_url

    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        path = "/integration/returns/series"
        url = f"{self._base_url}{path}"
        started_at = observation_start()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=request_payload, headers=headers)
                if response.status_code == 202:
                    accepted_payload = self._ensure_dict_payload(
                        response,
                        invalid_message="lotus-performance returned invalid async accepted payload",
                    )
                    payload = await self._poll_returns_series_result(
                        client=client,
                        accepted_payload=accepted_payload,
                        headers=headers,
                    )
                    record_upstream_request(
                        dependency="lotus-performance",
                        operation=path,
                        outcome="success",
                        category="ok",
                        started_at=started_at,
                    )
                    return payload
                response.raise_for_status()
                payload = self._ensure_dict_payload(
                    response,
                    invalid_message="lotus-performance returned invalid JSON payload",
                )
                record_upstream_request(
                    dependency="lotus-performance",
                    operation=path,
                    outcome="success",
                    category="ok",
                    started_at=started_at,
                )
                return payload
        except UpstreamServiceError as exc:
            self._record_upstream_failure(path, started_at=started_at, exc=exc)
            raise
        except httpx.HTTPStatusError as exc:
            detail = extract_upstream_error_detail(exc.response)
            error = classify_upstream_http_error(
                service="lotus-performance",
                operation=path,
                response=exc.response,
                detail=detail,
            )
            self._record_upstream_failure(path, started_at=started_at, exc=error)
            raise error from exc
        except httpx.HTTPError as exc:
            error = classify_upstream_transport_error(
                service="lotus-performance",
                operation=path,
                exc=exc,
            )
            self._record_upstream_failure(path, started_at=started_at, exc=error)
            raise error from exc

    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        path = "/integration/benchmarks/exposure-context"
        url = f"{self._base_url}{path}"
        started_at = observation_start()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=request_payload, headers=headers)
                response.raise_for_status()
                payload = self._ensure_dict_payload(
                    response,
                    invalid_message="lotus-performance returned invalid benchmark exposure context payload",
                )
                record_upstream_request(
                    dependency="lotus-performance",
                    operation=path,
                    outcome="success",
                    category="ok",
                    started_at=started_at,
                )
                return payload
        except UpstreamServiceError as exc:
            self._record_upstream_failure(path, started_at=started_at, exc=exc)
            raise
        except httpx.HTTPStatusError as exc:
            detail = extract_upstream_error_detail(exc.response)
            error = classify_upstream_http_error(
                service="lotus-performance",
                operation=path,
                response=exc.response,
                detail=detail,
            )
            self._record_upstream_failure(path, started_at=started_at, exc=error)
            raise error from exc
        except httpx.HTTPError as exc:
            error = classify_upstream_transport_error(
                service="lotus-performance",
                operation=path,
                exc=exc,
            )
            self._record_upstream_failure(path, started_at=started_at, exc=error)
            raise error from exc

    @staticmethod
    def _record_upstream_failure(
        operation: str,
        *,
        started_at: float,
        exc: UpstreamServiceError,
    ) -> None:
        category = exc.details.get("category")
        record_upstream_request(
            dependency="lotus-performance",
            operation=operation,
            outcome="failure",
            category=str(category or exc.code),
            started_at=started_at,
        )

    async def _poll_returns_series_result(
        self,
        *,
        client: httpx.AsyncClient,
        accepted_payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        result_path = accepted_payload.get("result_path")
        if not isinstance(result_path, str) or not result_path.startswith("/"):
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="lotus-performance async accepted payload missing result_path",
            )

        poll_path = accepted_payload.get("poll_path")
        if poll_path is not None and (
            not isinstance(poll_path, str) or not poll_path.startswith("/")
        ):
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/returns/series",
                message="lotus-performance async accepted payload has invalid poll_path",
            )

        last_status = "pending"
        for _ in range(self._async_max_polls):
            if poll_path:
                execution_payload = await self._get_dict(
                    client=client,
                    path=poll_path,
                    headers=headers,
                )
                status = execution_payload.get("status")
                if isinstance(status, str):
                    last_status = status
                if status == "failed":
                    error_message = execution_payload.get("error_message")
                    if isinstance(error_message, str) and error_message:
                        raise missing_upstream_data(
                            service="lotus-performance",
                            operation="/integration/returns/series",
                            message=f"lotus-performance async returns-series failed: {error_message}",
                        )
                    raise missing_upstream_data(
                        service="lotus-performance",
                        operation="/integration/returns/series",
                        message="lotus-performance async returns-series failed",
                    )

            result_response = await client.get(f"{self._base_url}{result_path}", headers=headers)
            if result_response.status_code == 200:
                return self._ensure_dict_payload(
                    result_response,
                    invalid_message="lotus-performance returned invalid async result payload",
                )
            if result_response.status_code not in {202, 404}:
                result_response.raise_for_status()
            await asyncio.sleep(self._async_poll_interval_seconds)

        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=(
                "lotus-performance async returns-series did not complete within polling budget "
                f"(last_status={last_status})"
            ),
        )

    async def _get_dict(
        self,
        *,
        client: httpx.AsyncClient,
        path: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        response = await client.get(f"{self._base_url}{path}", headers=headers)
        response.raise_for_status()
        return self._ensure_dict_payload(
            response,
            invalid_message=f"lotus-performance returned invalid JSON payload for {path}",
        )

    @staticmethod
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
