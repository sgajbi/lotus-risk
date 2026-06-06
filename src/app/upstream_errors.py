from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import httpx


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
        status_code=HTTPStatus.BAD_GATEWAY,
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
        status_code=HTTPStatus.FAILED_DEPENDENCY,
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


def _classified_http_error(
    *,
    service: str,
    operation: str,
    upstream_status: int,
    response_status: int,
    code: str,
    category: str,
    message: str,
    retryable: bool,
) -> UpstreamServiceError:
    return UpstreamServiceError(
        service=service,
        operation=operation,
        status_code=response_status,
        code=code,
        message=message,
        details=_dependency_details(
            service=service,
            operation=operation,
            category=category,
            extra={"upstream_status_code": upstream_status},
        ),
        retryable=retryable,
    )


def classify_upstream_http_error(
    *,
    service: str,
    operation: str,
    response: httpx.Response,
    detail: str,
) -> UpstreamServiceError:
    upstream_status = response.status_code
    if upstream_status == HTTPStatus.TOO_MANY_REQUESTS:
        return _classified_http_error(
            service=service,
            operation=operation,
            upstream_status=upstream_status,
            response_status=HTTPStatus.SERVICE_UNAVAILABLE,
            code="UPSTREAM_THROTTLED",
            message=f"{service} {operation} throttled ({upstream_status}): {detail}",
            category="throttled",
            retryable=True,
        )
    if upstream_status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return _classified_http_error(
            service=service,
            operation=operation,
            upstream_status=upstream_status,
            response_status=HTTPStatus.BAD_GATEWAY,
            code="UPSTREAM_FAILURE",
            message=f"{service} {operation} failed ({upstream_status}): {detail}",
            category="upstream_failure",
            retryable=True,
        )
    return _classified_http_error(
        service=service,
        operation=operation,
        upstream_status=upstream_status,
        response_status=HTTPStatus.FAILED_DEPENDENCY,
        code="FAILED_DEPENDENCY",
        message=f"{service} {operation} rejected request ({upstream_status}): {detail}",
        category="rejected_request",
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
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
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
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
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
