from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import app.dependencies.downstream_clients as downstream_clients


class _PerformanceClient:
    pass


class _CoreClient:
    pass


class _Request:
    def __init__(self) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace())


def test_resolve_downstream_clients_reuses_app_state_instances() -> None:
    request = _Request()
    request.app.state.lotus_performance_client = _PerformanceClient()
    request.app.state.lotus_core_client = _CoreClient()

    assert (
        downstream_clients.resolve_lotus_performance_client(cast(Any, request))
        is request.app.state.lotus_performance_client
    )
    assert (
        downstream_clients.resolve_lotus_core_client(cast(Any, request))
        is request.app.state.lotus_core_client
    )


def test_resolve_downstream_clients_falls_back_to_configured_classes() -> None:
    request = _Request()
    original_performance_class = getattr(downstream_clients, "LotusPerformanceClient")
    original_core_class = getattr(downstream_clients, "LotusCoreClient")

    try:
        setattr(downstream_clients, "LotusPerformanceClient", _PerformanceClient)
        setattr(downstream_clients, "LotusCoreClient", _CoreClient)

        assert isinstance(
            downstream_clients.resolve_lotus_performance_client(cast(Any, request)),
            _PerformanceClient,
        )
        assert isinstance(
            downstream_clients.resolve_lotus_core_client(cast(Any, request)),
            _CoreClient,
        )
    finally:
        setattr(downstream_clients, "LotusPerformanceClient", original_performance_class)
        setattr(downstream_clients, "LotusCoreClient", original_core_class)
