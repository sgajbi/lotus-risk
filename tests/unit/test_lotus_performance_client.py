from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any

import httpx
import pytest

from app.integrations.lotus_performance_client import (
    DEFAULT_LOTUS_PERFORMANCE_BASE_URL,
    LotusPerformanceClient,
)


class _FakeAsyncClient:
    response_factory: Callable[..., httpx.Response] | None = None
    last_request: dict[str, Any] | None = None
    requests: list[dict[str, Any]] = []

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
        request = {
            "method": "POST",
            "url": url,
            "json": json,
            "headers": headers,
        }
        _FakeAsyncClient.last_request = request
        _FakeAsyncClient.requests.append(request)
        assert _FakeAsyncClient.response_factory is not None
        return _FakeAsyncClient.response_factory(method="POST", url=url, json=json, headers=headers)

    async def get(self, url: str, *, headers: dict[str, str]) -> httpx.Response:
        request = {
            "method": "GET",
            "url": url,
            "headers": headers,
        }
        _FakeAsyncClient.last_request = request
        _FakeAsyncClient.requests.append(request)
        assert _FakeAsyncClient.response_factory is not None
        return _FakeAsyncClient.response_factory(method="GET", url=url, headers=headers)


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
    _FakeAsyncClient.requests = []
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
    _FakeAsyncClient.requests = []
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
    _FakeAsyncClient.requests = []
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


@pytest.mark.asyncio
async def test_client_maps_http_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenAsyncClient(_FakeAsyncClient):
        async def post(
            self, url: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> httpx.Response:
            raise httpx.ConnectError("network down", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", _BrokenAsyncClient)
    client = LotusPerformanceClient(base_url="http://performance.local")

    with pytest.raises(ValueError, match="unavailable"):
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )


@pytest.mark.asyncio
async def test_client_polls_async_returns_series_result_until_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    async def _no_sleep(*_: object) -> None:
        return None

    monkeypatch.setattr("app.integrations.lotus_performance_client.asyncio.sleep", _no_sleep)

    responses = iter(
        [
            _ok_response(
                {
                    "calculation_id": "calc-1",
                    "poll_path": "/performance/executions/calc-1",
                    "result_path": "/integration/returns/series/results/calc-1",
                },
                status_code=202,
                url="http://performance.local/integration/returns/series",
            ),
            _ok_response(
                {"status": "pending"},
                url="http://performance.local/performance/executions/calc-1",
            ),
            _ok_response(
                {"status": "pending"},
                status_code=202,
                url="http://performance.local/integration/returns/series/results/calc-1",
            ),
            _ok_response(
                {"status": "completed"},
                url="http://performance.local/performance/executions/calc-1",
            ),
            _ok_response(
                {"series": {"portfolio_returns": []}},
                url="http://performance.local/integration/returns/series/results/calc-1",
            ),
        ]
    )
    _FakeAsyncClient.response_factory = lambda **_: next(responses)

    client = LotusPerformanceClient(base_url="http://performance.local")
    response = await client.get_returns_series(
        request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
        correlation_id="corr-async",
    )

    assert response["series"] == {"portfolio_returns": []}
    assert [request["method"] for request in _FakeAsyncClient.requests] == [
        "POST",
        "GET",
        "GET",
        "GET",
        "GET",
    ]


@pytest.mark.asyncio
async def test_client_surfaces_async_execution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    responses = iter(
        [
            _ok_response(
                {
                    "calculation_id": "calc-1",
                    "poll_path": "/performance/executions/calc-1",
                    "result_path": "/integration/returns/series/results/calc-1",
                },
                status_code=202,
                url="http://performance.local/integration/returns/series",
            ),
            _ok_response(
                {
                    "status": "failed",
                    "error_message": "No benchmark assignment found for portfolio.",
                },
                url="http://performance.local/performance/executions/calc-1",
            ),
        ]
    )
    _FakeAsyncClient.response_factory = lambda **_: next(responses)

    client = LotusPerformanceClient(base_url="http://performance.local")
    with pytest.raises(
        ValueError,
        match="async returns-series failed: No benchmark assignment found for portfolio.",
    ):
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id="corr-async-fail",
        )


@pytest.mark.asyncio
async def test_client_times_out_async_returns_series_when_result_never_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    async def _no_sleep(*_: object) -> None:
        return None

    monkeypatch.setattr("app.integrations.lotus_performance_client.asyncio.sleep", _no_sleep)

    responses = iter(
        [
            _ok_response(
                {
                    "calculation_id": "calc-2",
                    "poll_path": "/performance/executions/calc-2",
                    "result_path": "/integration/returns/series/results/calc-2",
                },
                status_code=202,
                url="http://performance.local/integration/returns/series",
            ),
            _ok_response(
                {"status": "running"},
                url="http://performance.local/performance/executions/calc-2",
            ),
            _ok_response(
                {"status": "pending"},
                status_code=202,
                url="http://performance.local/integration/returns/series/results/calc-2",
            ),
            _ok_response(
                {"status": "running"},
                url="http://performance.local/performance/executions/calc-2",
            ),
            _ok_response(
                {"status": "pending"},
                status_code=202,
                url="http://performance.local/integration/returns/series/results/calc-2",
            ),
        ]
    )
    _FakeAsyncClient.response_factory = lambda **_: next(responses)

    client = LotusPerformanceClient(base_url="http://performance.local")
    client._async_max_polls = 2
    with pytest.raises(ValueError, match="did not complete within polling budget"):
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id="corr-async-timeout",
        )


def test_client_extract_error_detail_variants() -> None:
    response_plain = httpx.Response(
        status_code=500,
        text="plain text",
        request=httpx.Request("POST", "http://x"),
    )
    assert LotusPerformanceClient._extract_error_detail(response_plain) == "plain text"

    response_detail_str = _ok_response({"detail": "simple detail"})
    assert LotusPerformanceClient._extract_error_detail(response_detail_str) == "simple detail"

    response_error_obj = _ok_response({"error": {"message": "error message"}})
    assert LotusPerformanceClient._extract_error_detail(response_error_obj) == "error message"


def test_client_defaults_base_url_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOTUS_PERFORMANCE_BASE_URL", raising=False)
    client = LotusPerformanceClient()
    assert client._base_url == DEFAULT_LOTUS_PERFORMANCE_BASE_URL
