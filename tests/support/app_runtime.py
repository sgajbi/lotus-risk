from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Iterator, cast

from app.main import app
from app.runtime.downstream_clients import RuntimeDownstreamClients, runtime_downstream_clients


_UNSET = object()


@contextmanager
def override_app_runtime(
    *,
    lotus_performance_client: object = _UNSET,
    lotus_core_client: object = _UNSET,
    dependency_statuses: object = _UNSET,
) -> Iterator[None]:
    original_performance_client = getattr(app.state, "lotus_performance_client", None)
    original_core_client = getattr(app.state, "lotus_core_client", None)
    original_dependency_statuses = getattr(app.state, "dependency_statuses", None)
    original_runtime_override = app.dependency_overrides.get(runtime_downstream_clients, _UNSET)

    try:
        if lotus_performance_client is not _UNSET:
            app.state.lotus_performance_client = lotus_performance_client
        if lotus_core_client is not _UNSET:
            app.state.lotus_core_client = lotus_core_client
        if lotus_performance_client is not _UNSET or lotus_core_client is not _UNSET:
            app.dependency_overrides[runtime_downstream_clients] = lambda: RuntimeDownstreamClients(
                app_state=app.state
            )
        if dependency_statuses is not _UNSET:
            app.state.dependency_statuses = dependency_statuses
        yield
    finally:
        app.state.lotus_performance_client = original_performance_client
        app.state.lotus_core_client = original_core_client
        app.state.dependency_statuses = original_dependency_statuses
        if original_runtime_override is _UNSET:
            app.dependency_overrides.pop(runtime_downstream_clients, None)
        else:
            app.dependency_overrides[runtime_downstream_clients] = cast(
                Callable[..., Any],
                original_runtime_override,
            )
