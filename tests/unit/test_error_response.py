import json

from starlette.requests import Request

from app.error_response import build_error_payload, error_response


def _request(correlation_id: str) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    request.state.correlation_id = correlation_id
    return request


def test_build_error_payload_includes_correlation_and_details() -> None:
    payload = build_error_payload(
        _request("corr-unit"),
        code="INVALID_INPUT",
        message="bad input",
        details={"field": "periods"},
    )
    assert payload["error"]["code"] == "INVALID_INPUT"
    assert payload["error"]["message"] == "bad input"
    assert payload["error"]["correlation_id"] == "corr-unit"
    assert payload["error"]["details"] == {"field": "periods"}


def test_error_response_serializes_error_payload() -> None:
    response = error_response(
        _request("corr-json"),
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Not Found",
    )
    body = json.loads(bytes(response.body).decode("utf-8"))
    assert response.status_code == 404
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert body["error"]["correlation_id"] == "corr-json"
