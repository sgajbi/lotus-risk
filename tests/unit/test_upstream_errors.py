from __future__ import annotations

import httpx
import pytest
from fastapi import status

from app.upstream_errors import (
    classify_upstream_http_error,
    classify_upstream_transport_error,
    extract_upstream_error_detail,
    invalid_upstream_payload,
    missing_upstream_data,
)


def _response(status_code: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", "http://upstream.local/test"),
    )


@pytest.mark.parametrize(
    ("upstream_status", "expected_status", "expected_code", "expected_category", "retryable"),
    [
        (400, status.HTTP_424_FAILED_DEPENDENCY, "FAILED_DEPENDENCY", "rejected_request", False),
        (404, status.HTTP_424_FAILED_DEPENDENCY, "FAILED_DEPENDENCY", "rejected_request", False),
        (422, status.HTTP_424_FAILED_DEPENDENCY, "FAILED_DEPENDENCY", "rejected_request", False),
        (429, status.HTTP_503_SERVICE_UNAVAILABLE, "UPSTREAM_THROTTLED", "throttled", True),
        (500, status.HTTP_502_BAD_GATEWAY, "UPSTREAM_FAILURE", "upstream_failure", True),
        (503, status.HTTP_502_BAD_GATEWAY, "UPSTREAM_FAILURE", "upstream_failure", True),
        (504, status.HTTP_502_BAD_GATEWAY, "UPSTREAM_FAILURE", "upstream_failure", True),
    ],
)
def test_classify_upstream_http_error_matrix(
    upstream_status: int,
    expected_status: int,
    expected_code: str,
    expected_category: str,
    retryable: bool,
) -> None:
    error = classify_upstream_http_error(
        service="lotus-performance",
        operation="/integration/returns/series",
        response=_response(upstream_status, {"detail": {"message": "upstream detail"}}),
        detail="upstream detail",
    )

    assert error.status_code == expected_status
    assert error.code == expected_code
    assert error.retryable is retryable
    assert error.details == {
        "service": "lotus-performance",
        "operation": "/integration/returns/series",
        "category": expected_category,
        "upstream_status_code": upstream_status,
    }
    assert "upstream detail" in error.message


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code", "expected_category"),
    [
        (
            httpx.TimeoutException("timed out", request=httpx.Request("POST", "http://x")),
            status.HTTP_504_GATEWAY_TIMEOUT,
            "UPSTREAM_TIMEOUT",
            "timeout",
        ),
        (
            httpx.ConnectError("network down", request=httpx.Request("POST", "http://x")),
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "UPSTREAM_UNAVAILABLE",
            "transport",
        ),
    ],
)
def test_classify_upstream_transport_error_matrix(
    exc: httpx.HTTPError,
    expected_status: int,
    expected_code: str,
    expected_category: str,
) -> None:
    error = classify_upstream_transport_error(
        service="lotus-core",
        operation="/integration/reference/risk-free-series",
        exc=exc,
    )

    assert error.status_code == expected_status
    assert error.code == expected_code
    assert error.retryable is True
    assert error.details == {
        "service": "lotus-core",
        "operation": "/integration/reference/risk-free-series",
        "category": expected_category,
    }


def test_invalid_payload_and_missing_data_carry_structured_categories() -> None:
    invalid = invalid_upstream_payload(
        service="lotus-performance",
        operation="/integration/returns/series",
        message="invalid payload",
        details={"field": "series"},
    )
    missing = missing_upstream_data(
        service="lotus-core",
        operation="/integration/reference/risk-free-series",
        message="missing risk-free data",
        details={"currency": "USD"},
    )

    assert invalid.status_code == status.HTTP_502_BAD_GATEWAY
    assert invalid.code == "UPSTREAM_INVALID_RESPONSE"
    assert invalid.retryable is False
    assert invalid.details["category"] == "invalid_response"
    assert invalid.details["field"] == "series"
    assert missing.status_code == status.HTTP_424_FAILED_DEPENDENCY
    assert missing.code == "FAILED_DEPENDENCY"
    assert missing.retryable is False
    assert missing.details["category"] == "data_gap"
    assert missing.details["currency"] == "USD"


def test_extract_upstream_error_detail_variants() -> None:
    assert extract_upstream_error_detail(_response(400, {"detail": "simple detail"})) == (
        "simple detail"
    )
    assert extract_upstream_error_detail(_response(400, {"detail": {"message": "nested"}})) == (
        "nested"
    )
    assert extract_upstream_error_detail(_response(400, {"error": {"message": "error msg"}})) == (
        "error msg"
    )
    assert extract_upstream_error_detail(_response(400, {"unexpected": "payload"})) == str(
        {"unexpected": "payload"}
    )

    plain = httpx.Response(
        status_code=500,
        text="plain text",
        request=httpx.Request("POST", "http://x"),
    )
    assert extract_upstream_error_detail(plain) == "plain text"
