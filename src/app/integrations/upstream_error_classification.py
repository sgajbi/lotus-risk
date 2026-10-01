"""Classify HTTP-client failures at the downstream transport boundary."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus

import httpx

from app.upstream_errors import UpstreamServiceError, _dependency_details


@dataclass(frozen=True)
class _UpstreamHttpErrorProfile:
    response_status: int
    code: str
    category: str
    verb: str
    retryable: bool


def classify_upstream_http_error(
    *, service: str, operation: str, response: httpx.Response
) -> UpstreamServiceError:
    upstream_status = response.status_code
    profile = _upstream_http_error_profile(upstream_status)
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=profile.response_status,
        code=profile.code,
        message=f"{service} {operation} {profile.verb} ({upstream_status})",
        details=_dependency_details(
            service=service,
            operation=operation,
            category=profile.category,
            extra={"upstream_status_code": upstream_status},
        ),
        retryable=profile.retryable,
    )


def _upstream_http_error_profile(upstream_status: int) -> _UpstreamHttpErrorProfile:
    if upstream_status == HTTPStatus.TOO_MANY_REQUESTS:
        return _UpstreamHttpErrorProfile(
            response_status=HTTPStatus.SERVICE_UNAVAILABLE,
            code="UPSTREAM_THROTTLED",
            category="throttled",
            verb="throttled",
            retryable=True,
        )
    if upstream_status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return _UpstreamHttpErrorProfile(
            response_status=HTTPStatus.BAD_GATEWAY,
            code="UPSTREAM_FAILURE",
            category="upstream_failure",
            verb="failed",
            retryable=True,
        )
    return _UpstreamHttpErrorProfile(
        response_status=HTTPStatus.FAILED_DEPENDENCY,
        code="FAILED_DEPENDENCY",
        category="rejected_request",
        verb="rejected request",
        retryable=False,
    )


def classify_upstream_transport_error(
    *, service: str, operation: str, exc: httpx.HTTPError
) -> UpstreamServiceError:
    if isinstance(exc, httpx.TimeoutException):
        return UpstreamServiceError(
            service=service,
            operation=operation,
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
            code="UPSTREAM_TIMEOUT",
            message=f"{service} {operation} timed out",
            details=_dependency_details(
                service=service,
                operation=operation,
                category="timeout",
            ),
            retryable=True,
        )
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        code="UPSTREAM_UNAVAILABLE",
        message=f"{service} {operation} unavailable",
        details=_dependency_details(
            service=service,
            operation=operation,
            category="transport",
        ),
        retryable=True,
    )
