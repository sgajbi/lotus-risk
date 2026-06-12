import logging
from typing import Any, cast
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.correlation import CorrelationIdMiddleware


def _correlation_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware, service_name="lotus-risk")

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_resolve_trace_id_prefers_inbound_and_traceparent_fallback() -> None:
    inbound_trace_id = "a" * 32
    inbound = CorrelationIdMiddleware._resolve_trace_id(inbound_trace_id, None)
    assert inbound == inbound_trace_id

    extracted = CorrelationIdMiddleware._resolve_trace_id(
        None, "00-1234567890abcdef1234567890abcdef-0123456789abcdef-01"
    )
    assert extracted == "1234567890abcdef1234567890abcdef"


def test_resolve_trace_id_generates_when_traceparent_invalid() -> None:
    with patch("app.middleware.correlation.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "f" * 32
        trace_id = CorrelationIdMiddleware._resolve_trace_id(None, "invalid")
    assert trace_id == "f" * 32


def test_resolve_traceparent_uses_existing_or_generates() -> None:
    existing = "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"
    assert CorrelationIdMiddleware._resolve_traceparent(existing, "a" * 32) == existing

    with patch("app.middleware.correlation.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "1234567890abcdef1234567890abcdef"
        generated = CorrelationIdMiddleware._resolve_traceparent(None, "a" * 32)
    assert generated == f"00-{'a' * 32}-1234567890abcdef-01"


def test_resolve_traceparent_replaces_mismatched_or_malformed_headers() -> None:
    with patch("app.middleware.correlation.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "1234567890abcdef1234567890abcdef"
        mismatched = CorrelationIdMiddleware._resolve_traceparent(
            "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
            "c" * 32,
        )
        malformed = CorrelationIdMiddleware._resolve_traceparent("malformed", "d" * 32)

    assert mismatched == f"00-{'c' * 32}-1234567890abcdef-01"
    assert malformed == f"00-{'d' * 32}-1234567890abcdef-01"


def test_resolve_correlation_id_replaces_unbounded_or_unsafe_values() -> None:
    with patch("app.middleware.correlation.uuid.uuid4", return_value="generated-id"):
        assert CorrelationIdMiddleware._resolve_correlation_id("corr-123") == "corr-123"
        assert CorrelationIdMiddleware._resolve_correlation_id("x" * 129) == "generated-id"
        assert CorrelationIdMiddleware._resolve_correlation_id("unsafe value") == "generated-id"


def test_zero_trace_id_is_rejected() -> None:
    with patch("app.middleware.correlation.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "f" * 32
        trace_id = CorrelationIdMiddleware._resolve_trace_id("0" * 32, None)

    assert trace_id == "f" * 32


def test_correlation_middleware_sets_response_headers() -> None:
    client = TestClient(_correlation_app())
    response = client.get("/ping", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"
    assert response.headers["X-Trace-Id"]
    assert response.headers["traceparent"]
    assert response.headers["X-Service-Name"] == "lotus-risk"


def test_correlation_middleware_does_not_reflect_unsafe_context_headers() -> None:
    client = TestClient(_correlation_app())
    response = client.get(
        "/ping",
        headers={
            "X-Correlation-Id": "unsafe correlation value",
            "X-Trace-Id": "not-a-w3c-trace-id",
            "traceparent": "malformed",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] != "unsafe correlation value"
    assert response.headers["X-Trace-Id"] != "not-a-w3c-trace-id"
    assert response.headers["traceparent"] != "malformed"


def test_correlation_middleware_emits_bounded_structured_request_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="lotus_risk.request")
    client = TestClient(_correlation_app())

    response = client.get(
        "/ping?client_secret=do-not-log",
        headers={"X-Correlation-Id": "corr-structured"},
    )

    assert response.status_code == 200
    event = cast(dict[str, Any], getattr(caplog.records[-1], "request_observation"))
    assert event["service"] == "lotus-risk"
    assert event["method"] == "GET"
    assert event["path"] == "/ping"
    assert event["status_code"] == 200
    assert event["correlation_id"] == "corr-structured"
    assert event["risk"] is True
    assert "client_secret" not in str(event)
    assert "do-not-log" not in str(event)
