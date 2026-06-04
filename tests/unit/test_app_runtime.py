from __future__ import annotations

import app.routers.concentration as concentration_module
import app.routers.drawdown as drawdown_module
import app.routers.historical_attribution as historical_attribution_module
import app.routers.risk_calculation as risk_calculation_module
import app.routers.rolling as rolling_module
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
    original_dependency_statuses = getattr(app.state, "dependency_statuses", None)
    original_drawdown_performance_class = getattr(drawdown_module, "LotusPerformanceClient")
    original_attribution_performance_class = getattr(
        historical_attribution_module, "LotusPerformanceClient"
    )
    original_risk_performance_class = getattr(risk_calculation_module, "LotusPerformanceClient")
    original_rolling_performance_class = getattr(rolling_module, "LotusPerformanceClient")
    original_concentration_core_class = getattr(concentration_module, "LotusCoreClient")
    original_attribution_core_class = getattr(historical_attribution_module, "LotusCoreClient")
    original_rolling_core_class = getattr(rolling_module, "LotusCoreClient")

    with override_app_runtime(
        lotus_performance_client=_FakePerformanceClient(),
        lotus_core_client=_FakeCoreClient(),
        lotus_performance_class=_FakePerformanceClass,
        lotus_core_class=_FakeCoreClass,
        dependency_statuses={"lotus-core": {"status": "degraded"}},
    ):
        assert isinstance(app.state.lotus_performance_client, _FakePerformanceClient)
        assert isinstance(app.state.lotus_core_client, _FakeCoreClient)
        assert app.state.dependency_statuses == {"lotus-core": {"status": "degraded"}}
        assert getattr(drawdown_module, "LotusPerformanceClient") is _FakePerformanceClass
        assert (
            getattr(historical_attribution_module, "LotusPerformanceClient")
            is _FakePerformanceClass
        )
        assert getattr(risk_calculation_module, "LotusPerformanceClient") is _FakePerformanceClass
        assert getattr(rolling_module, "LotusPerformanceClient") is _FakePerformanceClass
        assert getattr(concentration_module, "LotusCoreClient") is _FakeCoreClass
        assert getattr(historical_attribution_module, "LotusCoreClient") is _FakeCoreClass
        assert getattr(rolling_module, "LotusCoreClient") is _FakeCoreClass

    assert app.state.lotus_performance_client is original_performance_client
    assert app.state.lotus_core_client is original_core_client
    assert app.state.dependency_statuses is original_dependency_statuses
    assert getattr(drawdown_module, "LotusPerformanceClient") is original_drawdown_performance_class
    assert (
        getattr(historical_attribution_module, "LotusPerformanceClient")
        is original_attribution_performance_class
    )
    assert (
        getattr(risk_calculation_module, "LotusPerformanceClient")
        is original_risk_performance_class
    )
    assert getattr(rolling_module, "LotusPerformanceClient") is original_rolling_performance_class
    assert getattr(concentration_module, "LotusCoreClient") is original_concentration_core_class
    assert (
        getattr(historical_attribution_module, "LotusCoreClient") is original_attribution_core_class
    )
    assert getattr(rolling_module, "LotusCoreClient") is original_rolling_core_class


def test_override_app_runtime_restores_state_after_exception() -> None:
    original_performance_client = getattr(app.state, "lotus_performance_client", None)
    original_attribution_core_class = getattr(historical_attribution_module, "LotusCoreClient")

    try:
        with override_app_runtime(
            lotus_performance_client=_FakePerformanceClient(),
            lotus_core_class=_FakeCoreClass,
        ):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert app.state.lotus_performance_client is original_performance_client
    assert (
        getattr(historical_attribution_module, "LotusCoreClient") is original_attribution_core_class
    )
