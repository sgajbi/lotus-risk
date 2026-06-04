from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import app.dependencies.downstream_clients as downstream_clients_module
from app.main import app


_UNSET = object()


@contextmanager
def override_app_runtime(
    *,
    lotus_performance_client: object = _UNSET,
    lotus_core_client: object = _UNSET,
    lotus_performance_class: object = _UNSET,
    lotus_core_class: object = _UNSET,
    dependency_statuses: object = _UNSET,
) -> Iterator[None]:
    original_performance_client = getattr(app.state, "lotus_performance_client", None)
    original_core_client = getattr(app.state, "lotus_core_client", None)
    original_dependency_statuses = getattr(app.state, "dependency_statuses", None)
    original_performance_class: Any = getattr(downstream_clients_module, "LotusPerformanceClient")
    original_core_class: Any = getattr(downstream_clients_module, "LotusCoreClient")

    try:
        if lotus_performance_client is not _UNSET:
            app.state.lotus_performance_client = lotus_performance_client
        if lotus_core_client is not _UNSET:
            app.state.lotus_core_client = lotus_core_client
        if lotus_performance_class is not _UNSET:
            setattr(
                downstream_clients_module,
                "LotusPerformanceClient",
                lotus_performance_class,
            )
        if lotus_core_class is not _UNSET:
            setattr(downstream_clients_module, "LotusCoreClient", lotus_core_class)
        if dependency_statuses is not _UNSET:
            app.state.dependency_statuses = dependency_statuses
        yield
    finally:
        app.state.lotus_performance_client = original_performance_client
        app.state.lotus_core_client = original_core_client
        app.state.dependency_statuses = original_dependency_statuses
        setattr(
            downstream_clients_module,
            "LotusPerformanceClient",
            original_performance_class,
        )
        setattr(downstream_clients_module, "LotusCoreClient", original_core_class)
