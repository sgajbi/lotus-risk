from __future__ import annotations

import httpx
import pytest

from tests.support.live_returns_series import (
    _request_json_with_retries,
    fetch_live_benchmark_exposure_context,
    fetch_live_risk_free_series,
)

pytestmark = pytest.mark.governance


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **_: object) -> httpx.Response:
        self.calls.append((method, url))
        return self._responses.pop(0)


def _response(status_code: int, payload: dict[str, object]) -> httpx.Response:
    request = httpx.Request("GET", "http://example.test/resource")
    return httpx.Response(status_code, json=payload, request=request)


def test_request_json_with_retries_returns_first_non_retryable_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tests.support.live_returns_series.time.sleep", lambda _: None)
    client = _FakeClient(
        [
            _response(503, {"detail": "warming"}),
            _response(200, {"series": {"portfolio_returns": []}}),
        ]
    )

    payload = _request_json_with_retries(
        client=client,
        method="GET",
        url="http://example.test/resource",
        max_attempts=3,
        retry_interval_seconds=0.0,
    )

    assert payload == {"series": {"portfolio_returns": []}}
    assert len(client.calls) == 2


def test_request_json_with_retries_raises_after_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tests.support.live_returns_series.time.sleep", lambda _: None)
    client = _FakeClient(
        [
            _response(503, {"detail": "warming"}),
            _response(503, {"detail": "still warming"}),
        ]
    )

    with pytest.raises(httpx.HTTPStatusError):
        _request_json_with_retries(
            client=client,
            method="GET",
            url="http://example.test/resource",
            max_attempts=2,
            retry_interval_seconds=0.0,
        )

    assert len(client.calls) == 2


def test_fetch_live_risk_free_series_uses_reference_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_request_json_with_retries(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"points": []}

    monkeypatch.setattr(
        "tests.support.live_returns_series._request_json_with_retries",
        _fake_request_json_with_retries,
    )

    payload = fetch_live_risk_free_series(
        base_url="http://core.example",
        request_payload={"currency": "USD"},
        request_attempts=7,
        retry_interval_seconds=0.25,
    )

    assert payload == {"points": []}
    assert captured["method"] == "POST"
    assert captured["url"] == "http://core.example/integration/reference/risk-free-series"
    assert captured["request_kwargs"] == {"json": {"currency": "USD"}}
    assert captured["max_attempts"] == 7
    assert captured["retry_interval_seconds"] == 0.25


def test_fetch_live_benchmark_exposure_context_uses_performance_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_request_json_with_retries(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"rows": []}

    monkeypatch.setattr(
        "tests.support.live_returns_series._request_json_with_retries",
        _fake_request_json_with_retries,
    )

    payload = fetch_live_benchmark_exposure_context(
        base_url="http://performance.example",
        request_payload={"portfolio_id": "PB_001"},
        request_attempts=4,
        retry_interval_seconds=0.5,
    )

    assert payload == {"rows": []}
    assert captured["method"] == "POST"
    assert captured["url"] == "http://performance.example/integration/benchmarks/exposure-context"
    assert captured["request_kwargs"] == {"json": {"portfolio_id": "PB_001"}}
    assert captured["max_attempts"] == 4
    assert captured["retry_interval_seconds"] == 0.5
