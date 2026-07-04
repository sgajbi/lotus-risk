from __future__ import annotations

from app.main import app
from app.runtime.downstream_clients import runtime_downstream_clients
from tests.support.app_runtime import override_app_runtime


class _FakePerformanceClient:
    pass


class _FakeCoreClient:
    pass


def test_override_app_runtime_restores_clients_and_runtime_override_after_exit() -> None:
    original_performance_client = getattr(app.state, "lotus_performance_client", None)
    original_core_client = getattr(app.state, "lotus_core_client", None)
    original_dependency_statuses = getattr(app.state, "dependency_statuses", None)
    original_runtime_override = app.dependency_overrides.get(runtime_downstream_clients)

    with override_app_runtime(
        lotus_performance_client=_FakePerformanceClient(),
        lotus_core_client=_FakeCoreClient(),
        dependency_statuses={"lotus-core": {"status": "degraded"}},
    ):
        assert isinstance(app.state.lotus_performance_client, _FakePerformanceClient)
        assert isinstance(app.state.lotus_core_client, _FakeCoreClient)
        assert app.state.dependency_statuses == {"lotus-core": {"status": "degraded"}}
        assert runtime_downstream_clients in app.dependency_overrides

    assert app.state.lotus_performance_client is original_performance_client
    assert app.state.lotus_core_client is original_core_client
    assert app.state.dependency_statuses is original_dependency_statuses
    assert app.dependency_overrides.get(runtime_downstream_clients) is original_runtime_override


def test_override_app_runtime_restores_state_after_exception() -> None:
    original_performance_client = getattr(app.state, "lotus_performance_client", None)
    original_runtime_override = app.dependency_overrides.get(runtime_downstream_clients)

    try:
        with override_app_runtime(
            lotus_performance_client=_FakePerformanceClient(),
        ):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert app.state.lotus_performance_client is original_performance_client
    assert app.dependency_overrides.get(runtime_downstream_clients) is original_runtime_override
