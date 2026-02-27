import logging
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enterprise_readiness import (
    authorize_write_request,
    build_enterprise_audit_middleware,
    emit_audit_event,
    load_feature_flags,
    redact_sensitive,
    validate_enterprise_runtime_config,
)


def test_validate_runtime_config_collects_and_enforces_issues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENTERPRISE_POLICY_VERSION", " ")
    monkeypatch.setenv("ENTERPRISE_SECRET_ROTATION_DAYS", "120")
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "true")
    monkeypatch.delenv("ENTERPRISE_PRIMARY_KEY_ID", raising=False)
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false")

    issues = validate_enterprise_runtime_config()
    assert sorted(issues) == sorted(
        [
            "missing_policy_version",
            "secret_rotation_days_out_of_range",
            "missing_primary_key_id",
        ]
    )

    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "true")
    with pytest.raises(RuntimeError, match="enterprise_runtime_config_invalid"):
        validate_enterprise_runtime_config()


def test_authorize_write_request_enforces_headers_identity_and_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "true")
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        '{"POST /analytics/risk/calculate":"risk.analytics.write"}',
    )
    allowed, reason = authorize_write_request("POST", "/analytics/risk/calculate", {})
    assert not allowed
    assert reason is not None and reason.startswith("missing_headers:")

    headers = {
        "X-Actor-Id": "actor-1",
        "X-Tenant-Id": "tenant-1",
        "X-Role": "advisor",
        "X-Correlation-Id": "corr-1",
    }
    allowed, reason = authorize_write_request("POST", "/analytics/risk/calculate", headers)
    assert not allowed
    assert reason == "missing_service_identity"

    headers["X-Service-Identity"] = "lotus-gateway"
    allowed, reason = authorize_write_request("POST", "/analytics/risk/calculate", headers)
    assert not allowed
    assert reason == "missing_capability:risk.analytics.write"

    headers["X-Capabilities"] = "risk.analytics.write"
    allowed, reason = authorize_write_request("POST", "/analytics/risk/calculate", headers)
    assert allowed
    assert reason is None

    allowed, reason = authorize_write_request("POST", "/unmapped/path", headers)
    assert allowed
    assert reason is None


def test_feature_flag_json_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTERPRISE_FEATURE_FLAGS_JSON", "invalid-json")
    assert load_feature_flags() == {}
    monkeypatch.setenv("ENTERPRISE_FEATURE_FLAGS_JSON", "[]")
    assert load_feature_flags() == {}


def test_redact_sensitive_masks_nested_structures() -> None:
    payload = {
        "authorization": "Bearer abc",
        "nested": {"client_email": "client@example.com", "safe": "ok"},
        "list": [{"token": "secret-token"}, {"value": 1}],
    }
    redacted = redact_sensitive(payload)
    assert redacted["authorization"] == "***REDACTED***"
    assert redacted["nested"]["client_email"] == "***REDACTED***"
    assert redacted["nested"]["safe"] == "ok"
    assert redacted["list"][0]["token"] == "***REDACTED***"


def test_emit_audit_event_redacts_metadata(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="enterprise_readiness")
    emit_audit_event(
        action="POST /analytics/risk/calculate",
        actor_id="actor-1",
        tenant_id="tenant-1",
        role="advisor",
        correlation_id=None,
        metadata={"token": "top-secret", "safe": {"ssn": "123-45-6789"}},
    )
    audit = cast(dict[str, Any], getattr(caplog.records[-1], "audit"))
    assert audit["correlation_id"] == ""
    assert audit["metadata"]["token"] == "***REDACTED***"
    assert audit["metadata"]["safe"]["ssn"] == "***REDACTED***"


def _enterprise_test_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(build_enterprise_audit_middleware())

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/writes")
    async def writes() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_enterprise_middleware_payload_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES", "1")
    client = TestClient(_enterprise_test_app())
    response = client.post(
        "/writes",
        content="too-large",
        headers={"X-Correlation-Id": "corr-413"},
    )
    assert response.status_code == 413
    body = response.json()["error"]
    assert body["code"] == "PAYLOAD_TOO_LARGE"
    assert body["message"] == "payload_too_large"
    assert body["correlationId"] == "corr-413"


def test_enterprise_middleware_denies_unauthorized_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "true")
    client = TestClient(_enterprise_test_app())
    response = client.post(
        "/writes",
        content="{}",
        headers={"X-Correlation-Id": "corr-403"},
    )
    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "AUTHORIZATION_DENIED"
    assert body["message"] == "authorization_policy_denied"
    assert body["details"]["reason"].startswith("missing_headers:")
    assert body["correlationId"] == "corr-403"


def test_enterprise_middleware_sets_policy_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "false")
    monkeypatch.setenv("ENTERPRISE_POLICY_VERSION", "2.0.0")
    client = TestClient(_enterprise_test_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Enterprise-Policy-Version"] == "2.0.0"


def test_enterprise_middleware_handles_invalid_numeric_env_and_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "false")
    monkeypatch.setenv("ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES", "not-an-int")
    client = TestClient(_enterprise_test_app())
    response = client.post("/writes", headers={"content-length": "not-an-int"}, content="ok")
    assert response.status_code == 200
