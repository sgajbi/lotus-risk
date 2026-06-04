"""Shared HTTP client profile helpers for downstream upstream adapters."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, TypeVar

import httpx
import os

from app.observability import record_upstream_request
from app.upstream_errors import (
    UpstreamServiceError,
    classify_upstream_http_error,
    classify_upstream_transport_error,
    extract_upstream_error_detail,
)


DEFAULT_TIMEOUT_SECONDS: Final = 10.0
DEFAULT_MAX_CONNECTIONS: Final = 100
DEFAULT_MAX_KEEPALIVE_CONNECTIONS: Final = 20
DEFAULT_KEEPALIVE_EXPIRY_SECONDS: Final = 5.0

_T = TypeVar("_T")


@dataclass(frozen=True)
class DownstreamClientProfile:
    timeout_seconds: float
    max_connections: int
    max_keepalive_connections: int
    keepalive_expiry_seconds: float

    def make_client(self) -> httpx.AsyncClient:
        limits = httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
            keepalive_expiry=self.keepalive_expiry_seconds,
        )
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            return httpx.AsyncClient(timeout=timeout, limits=limits)
        except TypeError:
            # Backward-compatible with older/mock AsyncClient implementations that do not
            # expose the `limits` keyword parameter in tests or constrained environments.
            return httpx.AsyncClient(timeout=timeout)


async def execute_downstream_request(
    *,
    dependency: str,
    operation: str,
    started_at: float,
    request_factory: Callable[[], Awaitable[httpx.Response]],
) -> httpx.Response:
    """Execute one outbound request and normalize failures into upstream errors."""
    try:
        response = await request_factory()
        response.raise_for_status()
        return response
    except UpstreamServiceError as exc:
        _record_upstream_failure(
            dependency=dependency,
            operation=operation,
            started_at=started_at,
            exc=exc,
        )
        raise
    except httpx.HTTPStatusError as exc:
        detail = extract_upstream_error_detail(exc.response)
        error = classify_upstream_http_error(
            service=dependency,
            operation=operation,
            response=exc.response,
            detail=detail,
        )
        _record_upstream_failure(
            dependency=dependency,
            operation=operation,
            started_at=started_at,
            exc=error,
        )
        raise error from exc
    except httpx.HTTPError as exc:
        error = classify_upstream_transport_error(
            service=dependency,
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


def _env_float_with_default(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int_with_default(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def resolve_downstream_client_profile(
    *,
    env_prefix: str,
    default_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    default_max_connections: int = DEFAULT_MAX_CONNECTIONS,
    default_max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    default_keepalive_expiry_seconds: float = DEFAULT_KEEPALIVE_EXPIRY_SECONDS,
) -> DownstreamClientProfile:
    return DownstreamClientProfile(
        timeout_seconds=_env_float_with_default(
            f"{env_prefix}_TIMEOUT_SECONDS", default_timeout_seconds
        ),
        max_connections=_env_int_with_default(
            f"{env_prefix}_MAX_CONNECTIONS", default_max_connections
        ),
        max_keepalive_connections=_env_int_with_default(
            f"{env_prefix}_MAX_KEEPALIVE_CONNECTIONS", default_max_keepalive_connections
        ),
        keepalive_expiry_seconds=_env_float_with_default(
            f"{env_prefix}_KEEPALIVE_EXPIRY_SECONDS", default_keepalive_expiry_seconds
        ),
    )
