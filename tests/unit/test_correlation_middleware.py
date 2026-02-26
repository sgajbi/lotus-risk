from unittest.mock import patch

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
    inbound = CorrelationIdMiddleware._resolve_trace_id("trace-1", None)
    assert inbound == "trace-1"

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
    assert CorrelationIdMiddleware._resolve_traceparent(existing, "ignored") == existing

    with patch("app.middleware.correlation.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "1234567890abcdef1234567890abcdef"
        generated = CorrelationIdMiddleware._resolve_traceparent(None, "traceid")
    assert generated == "00-traceid-1234567890abcdef-01"


def test_correlation_middleware_sets_response_headers() -> None:
    client = TestClient(_correlation_app())
    response = client.get("/ping", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"
    assert response.headers["X-Trace-Id"]
    assert response.headers["traceparent"]
    assert response.headers["X-Service-Name"] == "lotus-risk"
