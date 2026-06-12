"""Shared downstream request execution and upstream-error normalization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import NoReturn, TypeVar

import httpx

from app.observability import record_upstream_request
from app.upstream_errors import (
    UpstreamServiceError,
    classify_upstream_http_error,
    classify_upstream_transport_error,
)

_T = TypeVar("_T")


async def execute_downstream_request(
    *,
    dependency: str,
    operation: str,
    started_at: float,
    request_factory: Callable[[], Awaitable[httpx.Response]],
) -> httpx.Response:
    """Execute one outbound request and normalize failures into upstream errors."""
    try:
        return await _successful_downstream_response(request_factory)
    except UpstreamServiceError as exc:
        _raise_recorded_upstream_error(
            dependency=dependency,
            operation=operation,
            started_at=started_at,
            exc=exc,
        )
    except httpx.HTTPStatusError as exc:
        _raise_recorded_http_status_error(
            dependency=dependency,
            operation=operation,
            started_at=started_at,
            exc=exc,
        )
    except httpx.HTTPError as exc:
        _raise_recorded_transport_error(
            dependency=dependency,
            operation=operation,
            started_at=started_at,
            exc=exc,
        )


async def _successful_downstream_response(
    request_factory: Callable[[], Awaitable[httpx.Response]],
) -> httpx.Response:
    response = await request_factory()
    response.raise_for_status()
    return response


def _raise_recorded_upstream_error(
    *,
    dependency: str,
    operation: str,
    started_at: float,
    exc: UpstreamServiceError,
) -> NoReturn:
    _record_upstream_failure(
        dependency=dependency,
        operation=operation,
        started_at=started_at,
        exc=exc,
    )
    raise exc


def _raise_recorded_http_status_error(
    *,
    dependency: str,
    operation: str,
    started_at: float,
    exc: httpx.HTTPStatusError,
) -> NoReturn:
    error = _http_status_upstream_error(
        dependency=dependency,
        operation=operation,
        exc=exc,
    )
    _record_upstream_failure(
        dependency=dependency,
        operation=operation,
        started_at=started_at,
        exc=error,
    )
    raise error from exc


def _raise_recorded_transport_error(
    *,
    dependency: str,
    operation: str,
    started_at: float,
    exc: httpx.HTTPError,
) -> NoReturn:
    error = _transport_upstream_error(dependency=dependency, operation=operation, exc=exc)
    _record_upstream_failure(
        dependency=dependency,
        operation=operation,
        started_at=started_at,
        exc=error,
    )
    raise error from exc


def _http_status_upstream_error(
    *,
    dependency: str,
    operation: str,
    exc: httpx.HTTPStatusError,
) -> UpstreamServiceError:
    return classify_upstream_http_error(
        service=dependency,
        operation=operation,
        response=exc.response,
    )


def _transport_upstream_error(
    *,
    dependency: str,
    operation: str,
    exc: httpx.HTTPError,
) -> UpstreamServiceError:
    return classify_upstream_transport_error(
        service=dependency,
        operation=operation,
        exc=exc,
    )


async def execute_downstream_request_json(
    *,
    dependency: str,
    operation: str,
    started_at: float,
    request_factory: Callable[[], Awaitable[httpx.Response]],
    parse_response: Callable[[httpx.Response], _T],
    record_success: bool = True,
) -> _T:
    """Execute one outbound request, parse response JSON, and record supportability."""
    response = await execute_downstream_request(
        dependency=dependency,
        operation=operation,
        started_at=started_at,
        request_factory=request_factory,
    )
    try:
        parsed_response = parse_response(response)
    except UpstreamServiceError as exc:
        _record_upstream_failure(
            dependency=dependency,
            operation=operation,
            started_at=started_at,
            exc=exc,
        )
        raise
    if record_success:
        record_upstream_request(
            dependency=dependency,
            operation=operation,
            outcome="success",
            category="ok",
            started_at=started_at,
        )
    return parsed_response


def _record_upstream_failure(
    *,
    dependency: str,
    operation: str,
    started_at: float,
    exc: UpstreamServiceError,
) -> None:
    category = exc.details.get("category")
    record_upstream_request(
        dependency=dependency,
        operation=operation,
        outcome="failure",
        category=str(category or exc.code),
        started_at=started_at,
    )


__all__ = [
    "execute_downstream_request",
    "execute_downstream_request_json",
]
