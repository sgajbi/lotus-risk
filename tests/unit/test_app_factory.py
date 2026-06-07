from fastapi.testclient import TestClient
import pytest

from app.app_factory import create_app
from app.service_metadata import SERVICE_NAME, SERVICE_VERSION


def test_create_app_builds_independent_service_instance() -> None:
    first_app = create_app()
    second_app = create_app()

    first_app.state.lotus_core_client = object()

    assert first_app is not second_app
    assert not hasattr(second_app.state, "lotus_core_client")
    assert first_app.title == SERVICE_NAME
    assert first_app.version == SERVICE_VERSION


def test_create_app_registers_risk_analytics_routes() -> None:
    response = TestClient(create_app()).get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/analytics/risk/calculate" in paths
    assert "/analytics/risk/historical-attribution" in paths


def test_create_app_fails_closed_for_incomplete_enterprise_bank_posture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "true")
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "false")

    with pytest.raises(RuntimeError, match="authorization_not_enforced"):
        create_app()
