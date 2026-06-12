from __future__ import annotations

from typing import Any, NoReturn

import httpx

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


def parse_async_result_payload(
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


def async_returns_series_paths(accepted_payload: dict[str, Any]) -> tuple[str, str | None]:
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


def raise_returns_series_async_failure(execution_payload: dict[str, Any]) -> NoReturn:
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


def raise_returns_series_poll_timeout(last_status: str) -> NoReturn:
    raise missing_upstream_data(
        service="lotus-performance",
        operation=RETURNS_SERIES_OPERATION,
        message=(
            "lotus-performance async returns-series did not complete within polling budget "
            f"(last_status={last_status})"
        ),
    )


def required_async_result_payload(
    result_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if result_payload is not None:
        return result_payload
    raise missing_upstream_data(
        service="lotus-performance",
        operation=RETURNS_SERIES_OPERATION,
        message="lotus-performance async returns-series result returned no payload",
    )


__all__ = [
    "RETURNS_SERIES_OPERATION",
    "async_returns_series_paths",
    "ensure_dict_payload",
    "parse_async_result_payload",
    "raise_returns_series_async_failure",
    "raise_returns_series_poll_timeout",
    "required_async_result_payload",
]
