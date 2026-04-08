from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import httpx


RETRYABLE_STATUS_CODES = {502, 503, 504}


def _request_json_with_retries(
    *,
    client: httpx.Client,
    method: str,
    url: str,
    request_kwargs: dict[str, Any] | None = None,
    max_attempts: int,
    retry_interval_seconds: float,
) -> dict[str, Any]:
    kwargs = request_kwargs or {}
    last_response: httpx.Response | None = None
    for attempt in range(max_attempts):
        response = client.request(method, url, **kwargs)
        if response.status_code not in RETRYABLE_STATUS_CODES:
            response.raise_for_status()
            return response.json()
        last_response = response
        if attempt < max_attempts - 1:
            time.sleep(retry_interval_seconds)

    assert last_response is not None
    last_response.raise_for_status()
    raise AssertionError("unreachable")


def fetch_live_returns_series(
    *,
    base_url: str,
    request_payload: dict[str, Any],
    poll_attempts: int = 30,
    poll_interval_seconds: float = 1.0,
    request_attempts: int = 5,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        body = _request_json_with_retries(
            client=client,
            method="POST",
            url=f"{base_url}/integration/returns/series",
            request_kwargs={"json": request_payload},
            max_attempts=request_attempts,
            retry_interval_seconds=poll_interval_seconds,
        )

        if isinstance(body.get("series"), dict):
            return body

        result_path = body.get("result_path")
        if not isinstance(result_path, str):
            raise AssertionError("live returns-series response missing result_path")

        for _ in range(poll_attempts):
            result_body = _request_json_with_retries(
                client=client,
                method="GET",
                url=f"{base_url}{result_path}",
                max_attempts=request_attempts,
                retry_interval_seconds=poll_interval_seconds,
            )
            if isinstance(result_body.get("series"), dict):
                return result_body
            time.sleep(poll_interval_seconds)

    raise AssertionError("timed out waiting for live returns-series result")


def fetch_live_risk_free_series(
    *,
    base_url: str,
    request_payload: dict[str, Any],
    request_attempts: int = 5,
    retry_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        return _request_json_with_retries(
            client=client,
            method="POST",
            url=f"{base_url}/integration/reference/risk-free-series",
            request_kwargs={"json": request_payload},
            max_attempts=request_attempts,
            retry_interval_seconds=retry_interval_seconds,
        )


def fetch_live_benchmark_exposure_context(
    *,
    base_url: str,
    request_payload: dict[str, Any],
    request_attempts: int = 5,
    retry_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        return _request_json_with_retries(
            client=client,
            method="POST",
            url=f"{base_url}/integration/benchmarks/exposure-context",
            request_kwargs={"json": request_payload},
            max_attempts=request_attempts,
            retry_interval_seconds=retry_interval_seconds,
        )


def extract_decimal_returns(rows: Sequence[dict[str, Any]]) -> list[tuple[str, float]]:
    result: list[tuple[str, float]] = []
    for row in rows:
        date_value = row.get("date")
        return_value = row.get("return_value")
        if not isinstance(date_value, str):
            continue
        result.append((date_value, float(return_value)))
    return result
