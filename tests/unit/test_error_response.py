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
        status_code=400,
        code="INVALID_INPUT",
        message="bad input",
        details={"field": "periods"},
    )
    assert payload["error"]["type"] == "urn:lotus-risk:error:invalid-input"
    assert payload["error"]["title"] == "Invalid Input"
    assert payload["error"]["status"] == 400
    assert payload["error"]["detail"] == "bad input"
    assert payload["error"]["instance"] == "/"
    assert payload["error"]["code"] == "INVALID_INPUT"
    assert payload["error"]["message"] == "bad input"
    assert payload["error"]["correlation_id"] == "corr-unit"
    assert payload["error"]["details"] == {"field": "periods"}


def test_build_error_payload_preserves_legacy_shape_when_status_is_unknown() -> None:
    payload = build_error_payload(
        _request("corr-legacy"),
        code="INVALID_INPUT",
        message="bad input",
    )

    assert payload == {
        "error": {
            "code": "INVALID_INPUT",
            "message": "bad input",
            "correlation_id": "corr-legacy",
        }
    }


def test_error_response_serializes_error_payload() -> None:
    response = error_response(
        _request("corr-json"),
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Not Found",
    )
    body = json.loads(bytes(response.body).decode("utf-8"))
    assert response.status_code == 404
    assert body["error"]["type"] == "urn:lotus-risk:error:resource-not-found"
    assert body["error"]["title"] == "Resource Not Found"
    assert body["error"]["status"] == 404
    assert body["error"]["detail"] == "Not Found"
    assert body["error"]["instance"] == "/"
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert body["error"]["message"] == "Not Found"
    assert body["error"]["correlation_id"] == "corr-json"
