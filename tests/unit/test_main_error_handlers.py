import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast

from fastapi import HTTPException
import pytest
from starlette.requests import Request

from app.main import _default_error_code, analytics_risk_calculate, handle_http_exception


def _request_with_correlation(correlation_id: str = "corr-123") -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    request.state.correlation_id = correlation_id
    return request


def test_default_error_code_mapping() -> None:
    assert _default_error_code(404) == "RESOURCE_NOT_FOUND"
    assert _default_error_code(403) == "AUTHORIZATION_DENIED"
    assert _default_error_code(413) == "PAYLOAD_TOO_LARGE"
    assert _default_error_code(422) == "INVALID_REQUEST"
    assert _default_error_code(400) == "INVALID_INPUT"
    assert _default_error_code(500) == "REQUEST_REJECTED"


def test_handle_http_exception_returns_platform_error_envelope() -> None:
    request = _request_with_correlation()
    response = asyncio.run(
        handle_http_exception(request, HTTPException(status_code=400, detail="bad_input"))
    )
    body = json.loads(bytes(response.body).decode("utf-8"))
    assert response.status_code == 400
    assert body["error"]["code"] == "INVALID_INPUT"
    assert body["error"]["message"] == "bad_input"
    assert body["error"]["correlation_id"] == "corr-123"


def test_analytics_risk_calculate_unsupported_mode_guard_branch() -> None:
    request_payload = SimpleNamespace(input_mode=SimpleNamespace(value="unsupported_mode"))
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    with pytest.raises(ValueError, match="Unsupported input_mode=unsupported_mode"):
        asyncio.run(analytics_risk_calculate(cast(Any, request_payload), request))
