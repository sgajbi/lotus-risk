from __future__ import annotations

from typing import Any, ClassVar, NoReturn, cast

import httpx
import pytest
from fastapi import FastAPI

from app.app_lifecycle import application_lifespan
from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient


class _FakeHttpClient:
    def __init__(self, *, fail_close: bool = False) -> None:
        self.closed = False
        self.fail_close = fail_close

    async def aclose(self) -> None:
        self.closed = True
        if self.fail_close:
            raise RuntimeError("close failed")


class _FakeProfile:
    created_clients: ClassVar[list[_FakeHttpClient]] = []

    def make_client(self) -> _FakeHttpClient:
        client = _FakeHttpClient()
        self.created_clients.append(client)
        return client


def _resolve_fake_profile(**_: object) -> Any:
    return _FakeProfile()


def _reject_profile_resolution(**_: object) -> NoReturn:
    raise AssertionError("must not create runtime clients")


@pytest.mark.asyncio
async def test_application_lifespan_owns_reusable_downstream_http_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeProfile.created_clients = []
    monkeypatch.setattr(
        "app.app_lifecycle.resolve_downstream_client_profile",
        _resolve_fake_profile,
    )
    app = FastAPI()

    async with application_lifespan(app):
        assert isinstance(app.state.lotus_core_client, LotusCoreClient)
        assert isinstance(app.state.lotus_performance_client, LotusPerformanceClient)
        assert cast(httpx.AsyncClient, app.state.lotus_core_client._http_client) is cast(
            httpx.AsyncClient, _FakeProfile.created_clients[0]
        )
        assert cast(httpx.AsyncClient, app.state.lotus_performance_client._http_client) is cast(
            httpx.AsyncClient, _FakeProfile.created_clients[1]
        )
        assert app.state.is_draining is False

    assert app.state.is_draining is True
    assert all(client.closed for client in _FakeProfile.created_clients)
    assert not hasattr(app.state, "lotus_core_client")
    assert not hasattr(app.state, "lotus_performance_client")


@pytest.mark.asyncio
async def test_application_lifespan_preserves_injected_downstream_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.app_lifecycle.resolve_downstream_client_profile",
        _reject_profile_resolution,
    )
    core_client = object()
    performance_client = object()
    app = FastAPI()
    app.state.lotus_core_client = core_client
    app.state.lotus_performance_client = performance_client

    async with application_lifespan(app):
        assert app.state.lotus_core_client is core_client
        assert app.state.lotus_performance_client is performance_client

    assert app.state.lotus_core_client is core_client
    assert app.state.lotus_performance_client is performance_client


@pytest.mark.asyncio
async def test_application_lifespan_closes_all_owned_clients_when_one_close_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_client = _FakeHttpClient()
    second_client = _FakeHttpClient(fail_close=True)
    clients = iter([first_client, second_client])

    class _Profile:
        def make_client(self) -> Any:
            return next(clients)

    def _resolve_profile(**_: object) -> Any:
        return _Profile()

    monkeypatch.setattr(
        "app.app_lifecycle.resolve_downstream_client_profile",
        _resolve_profile,
    )
    app = FastAPI()

    async with application_lifespan(app):
        pass

    assert first_client.closed is True
    assert second_client.closed is True
