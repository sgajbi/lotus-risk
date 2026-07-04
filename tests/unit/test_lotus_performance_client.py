from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest
from prometheus_client import generate_latest

from app.integrations.lotus_performance_client import (
    DEFAULT_LOTUS_PERFORMANCE_BASE_URL,
    LotusPerformanceClient,
)
from app.integrations.lotus_performance_transport import (
    correlation_headers,
    resolve_lotus_performance_base_url,
)
from app.upstream_errors import UpstreamServiceError


class _FakeAsyncClient:
    response_factory: Callable[..., httpx.Response] | None = None
    last_request: dict[str, Any] | None = None
    requests: list[dict[str, Any]] = []

    def __init__(self, *, timeout: httpx.Timeout) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
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
    metrics = generate_latest().decode("utf-8")
    assert 'lotus_risk_upstream_requests_total{category="ok"' in metrics
    assert 'dependency="lotus-performance"' in metrics
    assert 'operation="/integration/returns/series"' in metrics


@pytest.mark.asyncio
async def test_client_reuses_injected_http_client_without_creating_temporary_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    injected_client = _FakeAsyncClient(timeout=httpx.Timeout(5.0))
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"series": {"portfolio_returns": []}}
    )
    monkeypatch.setattr(
        "app.integrations._downstream_client_profile.DownstreamClientProfile.make_client",
        lambda _: (_ for _ in ()).throw(AssertionError("temporary pool created")),
    )

    client = LotusPerformanceClient(
        base_url="http://performance.local",
        http_client=cast(httpx.AsyncClient, injected_client),
    )
    response = await client.get_returns_series(
        request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
        correlation_id=None,
    )

    assert response["series"] == {"portfolio_returns": []}


@pytest.mark.asyncio
async def test_client_rejects_non_object_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(["invalid"])
    client = LotusPerformanceClient(base_url="http://performance.local")

    with pytest.raises(UpstreamServiceError, match="invalid JSON payload") as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_client_maps_http_status_error_with_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"detail": {"message": "upstream failed"}},
        status_code=503,
    )
    client = LotusPerformanceClient(base_url="http://performance.local")

    with pytest.raises(UpstreamServiceError, match="failed \\(503\\)") as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
    assert exc_info.value.code == "UPSTREAM_FAILURE"
    assert exc_info.value.status_code == 502
    metrics = generate_latest().decode("utf-8")
    assert 'lotus_risk_upstream_requests_total{category="upstream_failure"' in metrics


@pytest.mark.asyncio
async def test_client_maps_http_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenAsyncClient(_FakeAsyncClient):
        async def post(
            self, url: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> httpx.Response:
            raise httpx.ConnectError("network down", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", _BrokenAsyncClient)
    client = LotusPerformanceClient(base_url="http://performance.local")

    with pytest.raises(UpstreamServiceError, match="unavailable") as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
    assert exc_info.value.code == "UPSTREAM_UNAVAILABLE"


@pytest.mark.asyncio
async def test_client_polls_async_returns_series_result_until_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    async def _no_sleep(*_: object) -> None:
        return None

    monkeypatch.setattr(
        "app.integrations.performance_returns_series_async.asyncio.sleep", _no_sleep
    )

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
                status_code=404,
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
    assert _FakeAsyncClient.requests[2]["url"].endswith(
        "/integration/returns/series/results/calc-1"
    )


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
        UpstreamServiceError,
        match="async returns-series failed: No benchmark assignment found for portfolio.",
    ) as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id="corr-async-fail",
        )
    assert exc_info.value.code == "FAILED_DEPENDENCY"


@pytest.mark.asyncio
async def test_client_surfaces_async_execution_failure_without_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    responses = iter(
        [
            _ok_response(
                {
                    "poll_path": "/performance/executions/calc-1",
                    "result_path": "/integration/returns/series/results/calc-1",
                },
                status_code=202,
            ),
            _ok_response({"status": "failed"}),
        ]
    )
    _FakeAsyncClient.response_factory = lambda **_: next(responses)

    client = LotusPerformanceClient(base_url="http://performance.local")
    with pytest.raises(UpstreamServiceError, match="async returns-series failed$") as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id="corr-async-fail",
        )
    assert exc_info.value.code == "FAILED_DEPENDENCY"


@pytest.mark.asyncio
async def test_client_rejects_null_async_result_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    async def _no_sleep(*_: object) -> None:
        return None

    monkeypatch.setattr(
        "app.integrations.performance_returns_series_async.asyncio.sleep", _no_sleep
    )

    responses = iter(
        [
            _ok_response(
                {
                    "result_path": "/integration/returns/series/results/calc-null",
                },
                status_code=202,
                url="http://performance.local/integration/returns/series",
            ),
            httpx.Response(
                200,
                content="null",
                request=httpx.Request(
                    "GET",
                    "http://performance.local/integration/returns/series/results/calc-null",
                ),
            ),
        ]
    )
    _FakeAsyncClient.response_factory = lambda **_: next(responses)

    client = LotusPerformanceClient(base_url="http://performance.local")
    with pytest.raises(
        UpstreamServiceError,
        match="result returned no payload",
    ) as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
    assert exc_info.value.code == "FAILED_DEPENDENCY"
    assert [request["method"] for request in _FakeAsyncClient.requests] == ["POST", "GET"]


@pytest.mark.asyncio
async def test_client_rejects_invalid_async_accepted_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    for payload, expected in [
        ({"result_path": "relative"}, "missing result_path"),
        ({"result_path": "/result", "poll_path": "relative"}, "invalid poll_path"),
    ]:

        def _response_factory(**_: Any) -> httpx.Response:
            return _ok_response(payload, status_code=202)

        _FakeAsyncClient.response_factory = _response_factory
        client = LotusPerformanceClient(base_url="http://performance.local")
        with pytest.raises(UpstreamServiceError, match=expected) as exc_info:
            await client.get_returns_series(
                request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
                correlation_id=None,
            )
        assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_client_raises_for_unexpected_async_result_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    responses = iter(
        [
            _ok_response(
                {"result_path": "/integration/returns/series/results/calc-1"},
                status_code=202,
            ),
            _ok_response({"detail": "not ready"}, status_code=500),
        ]
    )
    _FakeAsyncClient.response_factory = lambda **_: next(responses)

    client = LotusPerformanceClient(base_url="http://performance.local")
    with pytest.raises(UpstreamServiceError, match="failed \\(500\\)") as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
    assert exc_info.value.code == "UPSTREAM_FAILURE"
    assert "not ready" not in exc_info.value.message


@pytest.mark.asyncio
async def test_client_raises_for_unexpected_async_result_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    responses = iter(
        [
            _ok_response(
                {"result_path": "/integration/returns/series/results/calc-1"},
                status_code=202,
            ),
            _ok_response({"detail": "portfolio identifier leaked"}, status_code=400),
        ]
    )
    _FakeAsyncClient.response_factory = lambda **_: next(responses)

    client = LotusPerformanceClient(base_url="http://performance.local")
    with pytest.raises(UpstreamServiceError, match="rejected request \\(400\\)") as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
    assert exc_info.value.code == "FAILED_DEPENDENCY"
    assert "portfolio identifier leaked" not in exc_info.value.message


@pytest.mark.asyncio
async def test_client_times_out_async_returns_series_when_result_never_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []

    async def _no_sleep(*_: object) -> None:
        return None

    monkeypatch.setattr(
        "app.integrations.performance_returns_series_async.asyncio.sleep", _no_sleep
    )

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
    with pytest.raises(
        UpstreamServiceError, match="did not complete within polling budget"
    ) as exc_info:
        await client.get_returns_series(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id="corr-async-timeout",
        )
    assert exc_info.value.code == "FAILED_DEPENDENCY"


@pytest.mark.asyncio
async def test_client_builds_headers_and_payload_for_benchmark_exposure_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {
            "source_service": "lotus-performance",
            "contract_version": "v1",
            "rows": [],
            "metadata": {"source_system": "lotus-core", "served_by": "lotus-performance"},
        }
    )

    client = LotusPerformanceClient(base_url="http://performance.local", timeout_seconds=5)
    response = await client.get_benchmark_exposure_context(
        request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
        correlation_id="corr-benchmark-context",
    )

    assert response["source_service"] == "lotus-performance"
    assert _FakeAsyncClient.last_request is not None
    assert (
        _FakeAsyncClient.last_request["url"]
        == "http://performance.local/integration/benchmarks/exposure-context"
    )
    assert _FakeAsyncClient.last_request["headers"]["X-Correlation-Id"] == "corr-benchmark-context"
    assert _FakeAsyncClient.last_request["json"] == {"portfolio_id": "DEMO_DPM_EUR_001"}


@pytest.mark.asyncio
async def test_client_maps_benchmark_exposure_context_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response_factory = lambda **_: _ok_response(
        {"detail": {"message": "benchmark context unavailable"}},
        status_code=503,
    )
    client = LotusPerformanceClient(base_url="http://performance.local")

    with pytest.raises(
        UpstreamServiceError,
        match="exposure-context failed \\(503\\)",
    ) as exc_info:
        await client.get_benchmark_exposure_context(
            request_payload={"portfolio_id": "DEMO_DPM_EUR_001"},
            correlation_id=None,
        )
    assert exc_info.value.code == "UPSTREAM_FAILURE"


def test_client_defaults_base_url_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOTUS_PERFORMANCE_BASE_URL", raising=False)
    client = LotusPerformanceClient()
    assert client._base_url == DEFAULT_LOTUS_PERFORMANCE_BASE_URL


def test_resolve_lotus_performance_base_url_prefers_explicit_then_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_PERFORMANCE_BASE_URL", "http://env-performance.local/")

    assert resolve_lotus_performance_base_url("http://explicit-performance.local/") == (
        "http://explicit-performance.local"
    )
    assert resolve_lotus_performance_base_url(None) == "http://env-performance.local"


def test_correlation_headers_omits_empty_correlation_id() -> None:
    assert correlation_headers(None) == {}
    assert correlation_headers("corr-perf") == {"X-Correlation-Id": "corr-perf"}


def test_client_reads_async_polling_controls_with_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS", "2.5")
    monkeypatch.setenv("LOTUS_PERFORMANCE_ASYNC_MAX_POLLS", "33")
    client = LotusPerformanceClient(base_url="http://performance.local")
    assert client._async_poll_interval_seconds == 2.5
    assert client._async_max_polls == 33


def test_client_uses_fallbacks_for_invalid_async_polling_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS", "invalid")
    monkeypatch.setenv("LOTUS_PERFORMANCE_ASYNC_MAX_POLLS", "-7")
    client = LotusPerformanceClient(base_url="http://performance.local")
    assert client._async_poll_interval_seconds == 1.0
    assert client._async_max_polls == 60
