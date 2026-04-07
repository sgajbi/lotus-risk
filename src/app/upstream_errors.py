from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import status


@dataclass(slots=True)
class UpstreamServiceError(ValueError):
    service: str
    operation: str
    status_code: int
    code: str
    message: str
    details: dict[str, Any]
    retryable: bool

    def __str__(self) -> str:
        return self.message


def invalid_upstream_payload(
    *,
    service: str,
    operation: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> UpstreamServiceError:
    payload_details = {"service": service, "operation": operation}
    if details:
        payload_details.update(details)
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="UPSTREAM_INVALID_RESPONSE",
        message=message,
        details=payload_details,
        retryable=False,
    )


def missing_upstream_data(
    *,
    service: str,
    operation: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> UpstreamServiceError:
    payload_details = {"service": service, "operation": operation}
    if details:
        payload_details.update(details)
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=status.HTTP_424_FAILED_DEPENDENCY,
        code="FAILED_DEPENDENCY",
        message=message,
        details=payload_details,
        retryable=False,
    )


def classify_upstream_http_error(
    *,
    service: str,
    operation: str,
    response: httpx.Response,
    detail: str,
) -> UpstreamServiceError:
    upstream_status = response.status_code
    if upstream_status == status.HTTP_429_TOO_MANY_REQUESTS:
        return UpstreamServiceError(
            service=service,
            operation=operation,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="UPSTREAM_THROTTLED",
            message=f"{service} {operation} throttled ({upstream_status}): {detail}",
            details={
                "service": service,
                "operation": operation,
                "upstream_status_code": upstream_status,
            },
            retryable=True,
        )
    if upstream_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return UpstreamServiceError(
            service=service,
            operation=operation,
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="UPSTREAM_FAILURE",
            message=f"{service} {operation} failed ({upstream_status}): {detail}",
            details={
                "service": service,
                "operation": operation,
                "upstream_status_code": upstream_status,
            },
            retryable=True,
        )
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=status.HTTP_424_FAILED_DEPENDENCY,
        code="FAILED_DEPENDENCY",
        message=f"{service} {operation} rejected request ({upstream_status}): {detail}",
        details={
            "service": service,
            "operation": operation,
            "upstream_status_code": upstream_status,
        },
        retryable=False,
    )


def classify_upstream_transport_error(
    *,
    service: str,
    operation: str,
    exc: httpx.HTTPError,
) -> UpstreamServiceError:
    if isinstance(exc, httpx.TimeoutException):
        return UpstreamServiceError(
            service=service,
            operation=operation,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code="UPSTREAM_TIMEOUT",
            message=f"{service} {operation} timed out: {exc}",
            details={"service": service, "operation": operation},
            retryable=True,
        )
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="UPSTREAM_UNAVAILABLE",
        message=f"{service} {operation} unavailable: {exc}",
        details={"service": service, "operation": operation},
        retryable=True,
    )
