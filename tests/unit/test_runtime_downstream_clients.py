from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.runtime.downstream_clients import RuntimeCompositionError, RuntimeDownstreamClients


class _PerformanceClient:
    pass


class _CoreClient:
    pass


def test_runtime_downstream_clients_reuses_lifecycle_state_instances() -> None:
    state = SimpleNamespace(
        lotus_performance_client=_PerformanceClient(),
        lotus_core_client=_CoreClient(),
    )
    runtime_clients = RuntimeDownstreamClients(app_state=state)

    assert runtime_clients.lotus_performance() is state.lotus_performance_client
    assert runtime_clients.lotus_core() is state.lotus_core_client


@pytest.mark.parametrize(
    ("method_name", "dependency_name", "state_attribute"),
    (
        ("lotus_performance", "lotus-performance", "lotus_performance_client"),
        ("lotus_core", "lotus-core", "lotus_core_client"),
    ),
)
def test_runtime_downstream_clients_fail_closed_when_state_is_missing(
    method_name: str,
    dependency_name: str,
    state_attribute: str,
) -> None:
    runtime_clients = RuntimeDownstreamClients(app_state=SimpleNamespace())

    with pytest.raises(RuntimeCompositionError) as exc_info:
        getattr(runtime_clients, method_name)()

    assert exc_info.value.dependency_name == dependency_name
    assert exc_info.value.state_attribute == state_attribute
