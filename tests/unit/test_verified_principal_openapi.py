"""Registered OpenAPI outcomes and posture-specific authority, not runtime IAM proof."""

from copy import deepcopy
from typing import Any

import pytest

from app.app_factory import create_app
from app.contracts.error import ErrorResponse

PILOT_ROUTES = (
    "/analytics/risk/concentration",
    "/analytics/risk/regime-scenario-pack/evaluate",
    "/analytics/risk/risk-event-cohorts/evaluate",
)
VERIFIED_REASONS = {
    "missing_credential",
    "malformed_credential",
    "expired_credential",
    "revoked_principal",
}


@pytest.fixture(params=["header-trust", "verified"])
def schema(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", request.param)
    monkeypatch.setenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", "local")
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false")
    return create_app().openapi()


def assert_pilot_401(operation: dict[str, Any], route: str) -> None:
    assert "401" in operation["responses"], "missing actual 401 response"
    response = operation["responses"]["401"]
    assert "verified" in response["description"]
    assert response["headers"]["WWW-Authenticate"]["schema"]["const"] == "Bearer", (
        "incorrect challenge"
    )
    assert "verified" in response["headers"]["WWW-Authenticate"]["description"]
    content = response["content"]["application/json"]
    assert content["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
    examples = content["examples"]
    assert VERIFIED_REASONS <= examples.keys(), "missing verified refusal examples"
    for reason in VERIFIED_REASONS:
        model = ErrorResponse.model_validate(examples[reason]["value"])
        assert model.error.code == "AUTHORIZATION_DENIED", "incorrect denial envelope"
        assert model.error.message == model.error.detail == reason
        assert model.error.status == 401 and model.error.instance == route


@pytest.mark.parametrize("route", PILOT_ROUTES)
def test_registered_pilot_responses_publish_verified_401(
    schema: dict[str, Any], route: str
) -> None:
    assert_pilot_401(schema["paths"][route]["post"], route)


def assert_tenant_parameter(parameter: dict[str, Any]) -> None:
    assert parameter["required"] is False
    assert parameter["schema"] == {"type": "string", "minLength": 1, "maxLength": 128}
    for truth in (
        "LOTUS_RISK_PRINCIPAL_POSTURE=verified",
        "resolved credential",
        "X-Tenant-Id is ignored",
        "header-trust",
        "MISSING_TENANT_AUTHORITY",
        "INVALID_TENANT_AUTHORITY",
        "Stateless header-trust requests",
    ):
        assert truth in parameter["description"], "missing posture-specific tenant truth"


def test_registered_tenant_parameter_describes_both_postures(schema: dict[str, Any]) -> None:
    operation = schema["paths"][PILOT_ROUTES[0]]["post"]
    parameter = next(p for p in operation["parameters"] if p["name"] == "X-Tenant-Id")
    assert_tenant_parameter(parameter)
    legacy = operation["responses"]["401"]["content"]["application/json"]["examples"][
        "missing_tenant_authority"
    ]["value"]
    model = ErrorResponse.model_validate(legacy)
    assert model.error.code == "MISSING_TENANT_AUTHORITY"
    assert model.error.status == 401 and model.error.instance == PILOT_ROUTES[0]


def test_tenant_contract_guard_refuses_header_authority_mutation(schema: dict[str, Any]) -> None:
    operation = schema["paths"][PILOT_ROUTES[0]]["post"]
    parameter = deepcopy(next(p for p in operation["parameters"] if p["name"] == "X-Tenant-Id"))
    assert_tenant_parameter(parameter)
    parameter["description"] = "X-Tenant-Id supplies tenant authority in all postures."
    with pytest.raises(AssertionError, match="missing posture-specific tenant truth"):
        assert_tenant_parameter(parameter)


def test_unadopted_schema_contracts_are_not_promoted(schema: dict[str, Any]) -> None:
    mandate = schema["paths"]["/analytics/risk/mandate-health-context"]["post"]
    assert "401" not in mandate["responses"]
    assert mandate["x-lotus-verified-principal"]["adopted"] is False
    drawdown = schema["paths"]["/analytics/risk/drawdown"]["post"]
    assert (
        drawdown["responses"]["401"]["content"]["application/json"]["example"]["error"]["code"]
        == "MISSING_TENANT_AUTHORITY"
    )
    parameter = next(p for p in drawdown["parameters"] if p["name"] == "X-Tenant-Id")
    assert parameter["description"].startswith("Admitted tenant authority")
    assert "resolved credential" not in parameter["description"]


@pytest.mark.parametrize("mutation", ["response", "challenge", "envelope"])
def test_contract_guard_refuses_representative_schema_mutation(
    schema: dict[str, Any], mutation: str
) -> None:
    route = PILOT_ROUTES[1]
    operation = deepcopy(schema["paths"][route]["post"])
    assert_pilot_401(operation, route)
    if mutation == "response":
        del operation["responses"]["401"]
    elif mutation == "challenge":
        operation["responses"]["401"]["headers"]["WWW-Authenticate"]["schema"]["const"] = "Basic"
    else:
        operation["responses"]["401"]["content"]["application/json"]["examples"][
            "missing_credential"
        ]["value"]["error"]["code"] = "MISSING_TENANT_AUTHORITY"
    with pytest.raises(AssertionError):
        assert_pilot_401(operation, route)
