from __future__ import annotations

from typing import cast

import httpx
import pytest

from app.integrations._downstream_client_profile import (
    DownstreamClientProfile,
    execute_downstream_request,
    execute_downstream_request_json,
    resolve_downstream_client_profile,
)
from app.upstream_errors import UpstreamServiceError, invalid_upstream_payload


def _response(payload: object, *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", "http://downstream.local/example"),
    )


def test_resolve_downstream_client_profile_reads_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_CORE_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("LOTUS_CORE_MAX_CONNECTIONS", "77")
    monkeypatch.setenv("LOTUS_CORE_MAX_KEEPALIVE_CONNECTIONS", "33")
    monkeypatch.setenv("LOTUS_CORE_KEEPALIVE_EXPIRY_SECONDS", "14.5")

    profile = resolve_downstream_client_profile(
        env_prefix="LOTUS_CORE",
        default_timeout_seconds=10.0,
        default_max_connections=99,
        default_max_keepalive_connections=9,
        default_keepalive_expiry_seconds=9.0,
    )

    assert profile.timeout_seconds == 12.5
    assert profile.max_connections == 77
    assert profile.max_keepalive_connections == 33
    assert profile.keepalive_expiry_seconds == 14.5


def test_resolve_downstream_client_profile_defaults() -> None:
    profile = resolve_downstream_client_profile(
        env_prefix="LOTUS_PERFORMANCE",
        default_timeout_seconds=8.0,
        default_max_connections=12,
        default_max_keepalive_connections=3,
        default_keepalive_expiry_seconds=1.5,
    )

    assert profile.timeout_seconds == 8.0
    assert profile.max_connections == 12
    assert profile.max_keepalive_connections == 3
    assert profile.keepalive_expiry_seconds == 1.5


def test_resolve_downstream_client_profile_uses_fallback_when_values_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_CORE_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("LOTUS_CORE_MAX_CONNECTIONS", "zero")
    monkeypatch.setenv("LOTUS_CORE_MAX_KEEPALIVE_CONNECTIONS", "-8")
    monkeypatch.setenv("LOTUS_CORE_KEEPALIVE_EXPIRY_SECONDS", "0")

    profile = resolve_downstream_client_profile(
        env_prefix="LOTUS_CORE",
        default_timeout_seconds=9.0,
        default_max_connections=111,
        default_max_keepalive_connections=22,
        default_keepalive_expiry_seconds=3.0,
    )

    assert profile.timeout_seconds == 9.0
    assert profile.max_connections == 111
    assert profile.max_keepalive_connections == 22
    assert profile.keepalive_expiry_seconds == 3.0


def test_make_client_honors_profile_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeAsyncClient:
        last_init_kwargs: dict[str, object] = {}

        def __init__(self, **kwargs: object) -> None:
            self._init_kwargs = kwargs
            _FakeAsyncClient.last_init_kwargs = kwargs

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    profile = DownstreamClientProfile(
        timeout_seconds=7.5,
        max_connections=111,
        max_keepalive_connections=12,
        keepalive_expiry_seconds=4.25,
    )
    monkeypatch.setattr(
        "app.integrations._downstream_client_profile.httpx.AsyncClient", _FakeAsyncClient
    )
    profile.make_client()
    timeout = _FakeAsyncClient.last_init_kwargs["timeout"]
    limits = cast(
        httpx.Limits | None,
        _FakeAsyncClient.last_init_kwargs.get("limits"),
    )
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.__dict__["connect"] == 7.5
    if limits is not None:
        assert limits.max_connections == 111
        assert limits.max_keepalive_connections == 12
        assert limits.keepalive_expiry == 4.25


def test_make_client_falls_back_to_legacy_async_client_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatibility path should be used when httpx.AsyncClient lacks limits support."""

    class _LegacyAsyncClient:
        last_init_kwargs: dict[str, object] = {}

        def __init__(self, **kwargs: object) -> None:
            if "limits" in kwargs:
                raise TypeError("AsyncClient __init__ does not support limits")
            self._init_kwargs = kwargs
            _LegacyAsyncClient.last_init_kwargs = kwargs

        async def __aenter__(self) -> "_LegacyAsyncClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(
        "app.integrations._downstream_client_profile.httpx.AsyncClient", _LegacyAsyncClient
    )

    profile = DownstreamClientProfile(
        timeout_seconds=7.5,
        max_connections=111,
        max_keepalive_connections=12,
        keepalive_expiry_seconds=4.25,
    )

    profile.make_client()
    timeout = _LegacyAsyncClient.last_init_kwargs["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 7.5


@pytest.mark.asyncio
async def test_execute_downstream_request_json_records_success_and_parses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    success_records: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.integrations.downstream_request_execution.record_upstream_request",
        lambda **kwargs: success_records.append(kwargs),
    )

    async def _success_request_factory() -> httpx.Response:
        return _response({"ok": True})

    result = await execute_downstream_request_json(
        dependency="lotus-core",
        operation="/example",
        started_at=123.0,
        request_factory=_success_request_factory,
        parse_response=lambda response: {"ok": response.json()["ok"]},
    )

    assert result == {"ok": True}
    assert success_records
    assert success_records[0]["category"] == "ok"


@pytest.mark.asyncio
async def test_execute_downstream_request_json_allows_parser_owned_statuses() -> None:
    async def _accepted_request_factory() -> httpx.Response:
        return _response({"status": "pending"}, status_code=404)

    result = await execute_downstream_request_json(
        dependency="lotus-performance",
        operation="/integration/returns/series/results/calc-1",
        started_at=123.0,
        request_factory=_accepted_request_factory,
        parse_response=lambda response: (response.status_code, response.json()["status"]),
        accepted_status_codes={404},
        record_success=False,
    )

    assert result == (404, "pending")


@pytest.mark.asyncio
async def test_execute_downstream_request_json_records_failures_for_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failures: list[dict[str, object]] = []
    successes: list[dict[str, object]] = []

    monkeypatch.setattr(
        "app.integrations.downstream_request_execution._record_upstream_failure",
        lambda **kwargs: failures.append(kwargs),
    )
    monkeypatch.setattr(
        "app.integrations.downstream_request_execution.record_upstream_request",
        lambda **kwargs: successes.append(kwargs),
    )

    async def _invalid_request_factory() -> httpx.Response:
        return _response(["invalid"])

    with pytest.raises(UpstreamServiceError):
        await execute_downstream_request_json(
            dependency="lotus-core",
            operation="/example",
            started_at=999.0,
            request_factory=_invalid_request_factory,
            parse_response=lambda _: (_ for _ in ()).throw(
                invalid_upstream_payload(
                    service="lotus-core",
                    operation="/example",
                    message="invalid payload",
                )
            ),
        )

    assert failures
    assert failures[0]["dependency"] == "lotus-core"
    assert failures[0]["operation"] == "/example"
    assert not successes


@pytest.mark.asyncio
async def test_execute_downstream_request_maps_transport_and_http_failures() -> None:
    with pytest.raises(UpstreamServiceError, match="unavailable") as exc_info:
        await execute_downstream_request(
            dependency="lotus-core",
            operation="/example",
            started_at=100.0,
            request_factory=lambda: (_ for _ in ()).throw(
                httpx.ConnectError("network down", request=httpx.Request("POST", "http://x"))
            ),
        )
    assert exc_info.value.code == "UPSTREAM_UNAVAILABLE"
