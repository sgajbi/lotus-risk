from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from prometheus_client import generate_latest

from app.integrations.lotus_core_client import (
    DEFAULT_LOTUS_CORE_BASE_URL,
    LotusCoreClient,
)
from app.upstream_errors import UpstreamServiceError, extract_upstream_error_detail


class _FakeAsyncClient:
    response_factory: Callable[..., httpx.Response] | None = None
    last_request: dict[str, Any] | None = None

    def __init__(self, *, timeout: httpx.Timeout) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def request(
        self,
        *,
        method: str,
        url: str,
        json: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        _FakeAsyncClient.last_request = {
            "method": method,
            "url": url,
            "json": json,
            "headers": headers,
        }
        assert _FakeAsyncClient.response_factory is not None
        return _FakeAsyncClient.response_factory(method=method, url=url, json=json, headers=headers)


def _ok_response(
    payload: Any, *, status_code: int = 200, url: str = "http://localhost/mock"
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", url),
    )


@pytest.mark.asyncio
async def test_client_builds_headers_and_payload_for_session_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"session": {"session_id": "SIM_1"}}
    )

    client = LotusCoreClient(base_url="http://core.local", timeout_seconds=5)
    response = await client.create_simulation_session(
        portfolio_id="DEMO_DPM_EUR_001",
        ttl_hours=24,
        created_by="risk-agent",
        correlation_id="corr-123",
    )

    assert response["session"]["session_id"] == "SIM_1"
    assert _FakeAsyncClient.last_request is not None
    assert _FakeAsyncClient.last_request["url"] == "http://core.local/simulation-sessions"
    assert _FakeAsyncClient.last_request["json"]["ttl_hours"] == 24
    assert _FakeAsyncClient.last_request["json"]["created_by"] == "risk-agent"
    assert _FakeAsyncClient.last_request["headers"]["X-Correlation-Id"] == "corr-123"
    metrics = generate_latest().decode("utf-8")
    assert 'lotus_risk_upstream_requests_total{category="ok"' in metrics
    assert 'dependency="lotus-core"' in metrics
    assert 'operation="/simulation-sessions"' in metrics


@pytest.mark.asyncio
async def test_client_supports_add_changes_and_snapshot_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response({"ok": True})
    client = LotusCoreClient(base_url="http://core.local")

    add_response = await client.add_simulation_changes(
        session_id="SIM_1",
        changes=[{"security_id": "SEC_A", "transaction_type": "BUY"}],
        correlation_id=None,
    )
    snapshot_response = await client.get_core_snapshot(
        portfolio_id="DEMO_DPM_EUR_001",
        request_payload={"snapshot_mode": "BASELINE"},
        correlation_id=None,
    )
    enrichment_response = await client.get_instrument_enrichment(
        security_ids=["SEC_A", "SEC_B"],
        correlation_id=None,
    )
    position_timeseries_response = await client.get_position_analytics_timeseries(
        portfolio_id="DEMO_DPM_EUR_001",
        request_payload={"as_of_date": "2026-02-28"},
        correlation_id=None,
    )
    risk_free_response = await client.get_risk_free_series(
        request_payload={
            "currency": "USD",
            "as_of_date": "2026-01-04",
            "series_mode": "annualized_rate_series",
            "window": {"start_date": "2026-01-01", "end_date": "2026-01-04"},
            "frequency": "daily",
        },
        correlation_id=None,
    )
    risk_free_coverage_response = await client.get_risk_free_coverage(
        currency="USD",
        request_payload={
            "window": {"start_date": "2026-01-01", "end_date": "2026-01-04"},
        },
        correlation_id=None,
    )

    assert add_response == {"ok": True}
    assert snapshot_response == {"ok": True}
    assert enrichment_response == {"ok": True}
    assert position_timeseries_response == {"ok": True}
    assert risk_free_response == {"ok": True}
    assert risk_free_coverage_response == {"ok": True}
    assert _FakeAsyncClient.last_request is not None
    assert (
        _FakeAsyncClient.last_request["url"]
        == "http://core.local/integration/reference/risk-free-series/coverage?currency=USD"
    )


@pytest.mark.asyncio
async def test_client_rejects_non_object_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(["invalid"])
    client = LotusCoreClient(base_url="http://core.local")

    with pytest.raises(UpstreamServiceError, match="invalid JSON payload") as exc_info:
        await client.get_core_snapshot(
            portfolio_id="DEMO_DPM_EUR_001",
            request_payload={"snapshot_mode": "BASELINE"},
            correlation_id=None,
        )
    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_client_maps_http_status_error_with_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"detail": "bad request"},
        status_code=400,
    )
    client = LotusCoreClient(base_url="http://core.local")

    with pytest.raises(
        UpstreamServiceError, match="rejected request \\(400\\): bad request"
    ) as exc_info:
        await client.get_core_snapshot(
            portfolio_id="DEMO_DPM_EUR_001",
            request_payload={"snapshot_mode": "BASELINE"},
            correlation_id=None,
        )
    assert exc_info.value.code == "FAILED_DEPENDENCY"
    assert exc_info.value.status_code == 424


@pytest.mark.asyncio
async def test_client_maps_http_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenAsyncClient(_FakeAsyncClient):
        async def request(
            self,
            *,
            method: str,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> httpx.Response:
            raise httpx.ConnectError("network down", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "AsyncClient", _BrokenAsyncClient)
    client = LotusCoreClient(base_url="http://core.local")

    with pytest.raises(UpstreamServiceError, match="unavailable") as exc_info:
        await client.get_core_snapshot(
            portfolio_id="DEMO_DPM_EUR_001",
            request_payload={"snapshot_mode": "BASELINE"},
            correlation_id=None,
        )
    assert exc_info.value.code == "UPSTREAM_UNAVAILABLE"
    assert exc_info.value.status_code == 503


def test_extract_error_detail_variants() -> None:
    response_plain = httpx.Response(
        status_code=500,
        text="plain text",
        request=httpx.Request("POST", "http://x"),
    )
    assert extract_upstream_error_detail(response_plain) == "plain text"

    response_dict = _ok_response({"detail": {"message": "nested message"}})
    assert extract_upstream_error_detail(response_dict) == "nested message"


def test_client_defaults_to_canonical_core_service_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOTUS_CORE_BASE_URL", raising=False)

    client = LotusCoreClient()

    assert DEFAULT_LOTUS_CORE_BASE_URL == "http://core-control.dev.lotus"
    assert client._base_url == DEFAULT_LOTUS_CORE_BASE_URL
