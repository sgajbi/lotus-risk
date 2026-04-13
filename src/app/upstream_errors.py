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


def _dependency_details(
    *,
    service: str,
    operation: str,
    category: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "service": service,
        "operation": operation,
        "category": category,
    }
    if extra:
        details.update(extra)
    return details


def invalid_upstream_payload(
    *,
    service: str,
    operation: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> UpstreamServiceError:
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="UPSTREAM_INVALID_RESPONSE",
        message=message,
        details=_dependency_details(
            service=service,
            operation=operation,
            category="invalid_response",
            extra=details,
        ),
        retryable=False,
    )


def missing_upstream_data(
    *,
    service: str,
    operation: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> UpstreamServiceError:
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=status.HTTP_424_FAILED_DEPENDENCY,
        code="FAILED_DEPENDENCY",
        message=message,
        details=_dependency_details(
            service=service,
            operation=operation,
            category="data_gap",
            extra=details,
        ),
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
            details=_dependency_details(
                service=service,
                operation=operation,
                category="throttled",
                extra={"upstream_status_code": upstream_status},
            ),
            retryable=True,
        )
    if upstream_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return UpstreamServiceError(
            service=service,
            operation=operation,
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="UPSTREAM_FAILURE",
            message=f"{service} {operation} failed ({upstream_status}): {detail}",
            details=_dependency_details(
                service=service,
                operation=operation,
                category="upstream_failure",
                extra={"upstream_status_code": upstream_status},
            ),
            retryable=True,
        )
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=status.HTTP_424_FAILED_DEPENDENCY,
        code="FAILED_DEPENDENCY",
        message=f"{service} {operation} rejected request ({upstream_status}): {detail}",
        details=_dependency_details(
            service=service,
            operation=operation,
            category="rejected_request",
            extra={"upstream_status_code": upstream_status},
        ),
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
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="UPSTREAM_UNAVAILABLE",
        message=f"{service} {operation} unavailable: {exc}",
        details=_dependency_details(
            service=service,
            operation=operation,
            category="transport",
        ),
        retryable=True,
    )


def extract_upstream_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "unknown error"
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict):
            message = detail.get("message")
            if isinstance(message, str):
                return message
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
    return str(payload)
