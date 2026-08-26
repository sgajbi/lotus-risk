from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.integrations._downstream_client_profile import resolve_downstream_client_profile
from app.integrations.lotus_core_client import LotusCoreClient
from app.integrations.lotus_performance_client import LotusPerformanceClient

logger = logging.getLogger("app_lifecycle")


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own reusable downstream HTTP pools for the application process lifetime."""
    app.state.is_draining = False
    owned_http_clients: list[tuple[str, httpx.AsyncClient]] = []
    try:
        if not hasattr(app.state, "lotus_core_client"):
            core_http_client = resolve_downstream_client_profile(
                env_prefix="LOTUS_CORE"
            ).make_client()
            app.state.lotus_core_client = LotusCoreClient(http_client=core_http_client)
            owned_http_clients.append(("lotus_core_client", core_http_client))
        if not hasattr(app.state, "lotus_performance_client"):
            performance_http_client = resolve_downstream_client_profile(
                env_prefix="LOTUS_PERFORMANCE"
            ).make_client()
            app.state.lotus_performance_client = LotusPerformanceClient(
                http_client=performance_http_client
            )
            owned_http_clients.append(("lotus_performance_client", performance_http_client))
        yield
    finally:
        app.state.is_draining = True
        await _close_owned_http_clients(app, owned_http_clients)


async def _close_owned_http_clients(
    app: FastAPI,
    owned_http_clients: list[tuple[str, httpx.AsyncClient]],
) -> None:
    for state_attribute, http_client in reversed(owned_http_clients):
        try:
            await http_client.aclose()
        # Shutdown must attempt to close both downstream clients regardless of one adapter's
        # concrete close failure type.
        except Exception:  # noqa: BLE001
            logger.error(
                "downstream_http_client_close_failed",
                extra={"state_attribute": state_attribute},
            )
        finally:
            delattr(app.state, state_attribute)
