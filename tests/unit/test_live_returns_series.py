from __future__ import annotations

import httpx
import pytest

from tests.support.live_returns_series import _request_json_with_retries


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


def test_request_json_with_retries_returns_first_non_retryable_success(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_request_json_with_retries_raises_after_retry_budget(monkeypatch: pytest.MonkeyPatch) -> None:
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
