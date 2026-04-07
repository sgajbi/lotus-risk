from __future__ import annotations

import app.main as main_module
from app.main import app
from tests.support.app_runtime import override_app_runtime


class _FakePerformanceClient:
    pass


class _FakeCoreClient:
    pass


class _FakePerformanceClass:
    pass


class _FakeCoreClass:
    pass


def test_override_app_runtime_restores_clients_and_classes_after_exit() -> None:
    original_performance_client = getattr(app.state, "lotus_performance_client", None)
    original_core_client = getattr(app.state, "lotus_core_client", None)
    original_performance_class = getattr(main_module, "LotusPerformanceClient")
    original_core_class = getattr(main_module, "LotusCoreClient")

    with override_app_runtime(
        lotus_performance_client=_FakePerformanceClient(),
        lotus_core_client=_FakeCoreClient(),
        lotus_performance_class=_FakePerformanceClass,
        lotus_core_class=_FakeCoreClass,
    ):
        assert isinstance(app.state.lotus_performance_client, _FakePerformanceClient)
        assert isinstance(app.state.lotus_core_client, _FakeCoreClient)
        assert getattr(main_module, "LotusPerformanceClient") is _FakePerformanceClass
        assert getattr(main_module, "LotusCoreClient") is _FakeCoreClass

    assert app.state.lotus_performance_client is original_performance_client
    assert app.state.lotus_core_client is original_core_client
    assert getattr(main_module, "LotusPerformanceClient") is original_performance_class
    assert getattr(main_module, "LotusCoreClient") is original_core_class


def test_override_app_runtime_restores_state_after_exception() -> None:
    original_performance_client = getattr(app.state, "lotus_performance_client", None)
    original_core_class = getattr(main_module, "LotusCoreClient")

    try:
        with override_app_runtime(
            lotus_performance_client=_FakePerformanceClient(),
            lotus_core_class=_FakeCoreClass,
        ):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert app.state.lotus_performance_client is original_performance_client
    assert getattr(main_module, "LotusCoreClient") is original_core_class
