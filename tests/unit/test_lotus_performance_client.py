from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any

import httpx
import pytest

from app.integrations.lotus_performance_client import LotusPerformanceClient


class _FakeAsyncClient:
    response_factory: Callable[..., httpx.Response] | None = None
    last_request: dict[str, Any] | None = None

    def __init__(self, *, timeout: httpx.Timeout) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def post(
        self, url: str, *, json: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        _FakeAsyncClient.last_request = {
            "url": url,
            "json": json,
            "headers": headers,
        }
        assert _FakeAsyncClient.response_factory is not None
        return _FakeAsyncClient.response_factory(url=url, json=json, headers=headers)


def _ok_response(
    payload: Any, *, status_code: int = 200, url: str = "http://localhost/mock"
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", url),
    )


@pytest.mark.asyncio
async def test_client_builds_headers_and_payload_for_returns_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"series": {"portfolio_returns": []}}
    )

    client = LotusPerformanceClient(base_url="http://performance.local", timeout_seconds=5)
    response = await client.get_returns_series(
        request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
        correlation_id="corr-123",
    )

    assert response["series"] == {"portfolio_returns": []}
    assert _FakeAsyncClient.last_request is not None
    assert (
        _FakeAsyncClient.last_request["url"]
        == "http://performance.local/integration/returns/series"
    )
    assert _FakeAsyncClient.last_request["headers"]["X-Correlation-Id"] == "corr-123"


@pytest.mark.asyncio
async def test_client_rejects_non_object_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(["invalid"])
    client = LotusPerformanceClient(base_url="http://performance.local")

    with pytest.raises(ValueError, match="invalid JSON payload"):
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )


@pytest.mark.asyncio
async def test_client_maps_http_status_error_with_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"detail": {"message": "upstream failed"}},
        status_code=503,
    )
    client = LotusPerformanceClient(base_url="http://performance.local")

    with pytest.raises(ValueError, match="failed \\(503\\): upstream failed"):
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
