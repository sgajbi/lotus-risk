import logging
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enterprise_readiness import (
    authorize_write_request,
    build_enterprise_audit_middleware,
    emit_audit_event,
    load_capability_rules,
    load_feature_flags,
    redact_sensitive,
    validate_enterprise_runtime_config,
)
from app.enterprise_authorization import (
    SUPPORTED_WRITE_ROUTES,
    missing_supported_write_route_capability_rules,
)


def _set_valid_enterprise_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "ENTERPRISE_ENFORCE_RUNTIME_CONFIG": "true",
        "ENTERPRISE_ENFORCE_AUTHZ": "true",
        "ENTERPRISE_POLICY_VERSION": "2.0.0",
        "ENTERPRISE_PRIMARY_KEY_ID": "key-2026-01",
        "ENTERPRISE_SECRET_ROTATION_DAYS": "30",
        "ENTERPRISE_CAPABILITY_RULES_JSON": ('{"POST /analytics/risk":"risk.analytics.write"}'),
        "ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES": "1048576",
        "LOTUS_CORE_BASE_URL": "https://core.internal.example",
        "LOTUS_PERFORMANCE_BASE_URL": "https://performance.internal.example",
    }.items():
        monkeypatch.setenv(name, value)


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


def test_validate_enterprise_runtime_config_accepts_complete_bank_posture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_valid_enterprise_runtime_config(monkeypatch)

    assert validate_enterprise_runtime_config() == []


def test_supported_write_route_inventory_covers_current_analytics_posts() -> None:
    assert SUPPORTED_WRITE_ROUTES == (
        ("POST", "/analytics/risk/calculate"),
        ("POST", "/analytics/risk/concentration"),
        ("POST", "/analytics/risk/drawdown"),
        ("POST", "/analytics/risk/historical-attribution"),
        ("POST", "/analytics/risk/mandate-health-context"),
        ("POST", "/analytics/risk/regime-scenario-pack/evaluate"),
        ("POST", "/analytics/risk/risk-event-cohorts/evaluate"),
        ("POST", "/analytics/risk/rolling-metrics"),
    )


def test_enterprise_runtime_config_fails_when_write_route_capability_is_unmapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_valid_enterprise_runtime_config(monkeypatch)
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        '{"POST /analytics/risk/calculate":"risk.analytics.write"}',
    )

    with pytest.raises(
        RuntimeError,
        match="missing_capability_rule:POST /analytics/risk/drawdown",
    ):
        validate_enterprise_runtime_config()


def test_capability_rule_coverage_supports_prefix_rules() -> None:
    assert (
        missing_supported_write_route_capability_rules(
            {"POST /analytics/risk": "risk.analytics.write"}
        )
        == []
    )


@pytest.mark.parametrize(
    ("setting", "value", "issue"),
    [
        ("ENTERPRISE_ENFORCE_AUTHZ", "false", "authorization_not_enforced"),
        ("ENTERPRISE_POLICY_VERSION", "", "missing_policy_version"),
        ("ENTERPRISE_PRIMARY_KEY_ID", "", "missing_primary_key_id"),
        ("ENTERPRISE_SECRET_ROTATION_DAYS", "", "missing_secret_rotation_days"),
        ("ENTERPRISE_CAPABILITY_RULES_JSON", "{}", "missing_capability_rules"),
        (
            "ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES",
            "0",
            "missing_or_invalid_max_write_payload_bytes",
        ),
        ("LOTUS_CORE_BASE_URL", "", "missing_lotus_core_base_url"),
        ("LOTUS_PERFORMANCE_BASE_URL", "", "missing_lotus_performance_base_url"),
    ],
)
def test_validate_enterprise_runtime_config_fails_closed_for_missing_bank_posture(
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    value: str,
    issue: str,
) -> None:
    _set_valid_enterprise_runtime_config(monkeypatch)
    monkeypatch.setenv(setting, value)

    with pytest.raises(RuntimeError, match=issue):
        validate_enterprise_runtime_config()


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("LOTUS_CORE_TIMEOUT_SECONDS", "not-a-number"),
        ("LOTUS_CORE_MAX_CONNECTIONS", "0"),
        ("LOTUS_CORE_MAX_KEEPALIVE_CONNECTIONS", "-1"),
        ("LOTUS_CORE_KEEPALIVE_EXPIRY_SECONDS", "nan"),
        ("LOTUS_PERFORMANCE_TIMEOUT_SECONDS", "inf"),
        ("LOTUS_PERFORMANCE_MAX_CONNECTIONS", "0"),
        ("LOTUS_PERFORMANCE_MAX_KEEPALIVE_CONNECTIONS", "-1"),
        ("LOTUS_PERFORMANCE_KEEPALIVE_EXPIRY_SECONDS", ""),
        ("LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS", "0"),
        ("LOTUS_PERFORMANCE_ASYNC_MAX_POLLS", "1.5"),
    ],
)
def test_validate_enterprise_runtime_config_rejects_invalid_downstream_overrides(
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    value: str,
) -> None:
    _set_valid_enterprise_runtime_config(monkeypatch)
    monkeypatch.setenv(setting, value)

    with pytest.raises(RuntimeError) as exc_info:
        validate_enterprise_runtime_config()

    error = str(exc_info.value)
    assert f"invalid_downstream_runtime_setting:{setting}" in error
    if value:
        assert value not in error


def test_validate_runtime_config_preserves_local_downstream_override_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_valid_enterprise_runtime_config(monkeypatch)
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false")
    monkeypatch.setenv("LOTUS_CORE_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("LOTUS_PERFORMANCE_ASYNC_MAX_POLLS", "-7")

    assert validate_enterprise_runtime_config() == []


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
    assert not allowed
    assert reason == "missing_capability_rule"

    allowed, reason = authorize_write_request("POST", "/analytics/risk/calculate-extra", headers)
    assert not allowed
    assert reason == "missing_capability_rule"


def test_feature_flag_json_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTERPRISE_FEATURE_FLAGS_JSON", "invalid-json")
    assert load_feature_flags() == {}
    monkeypatch.setenv("ENTERPRISE_FEATURE_FLAGS_JSON", "[]")
    assert load_feature_flags() == {}


def test_capability_rules_accept_only_nonempty_string_mappings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        (
            '{"POST /valid":"risk.write","GET /read":"risk.read","invalid":"risk.write",'
            '"POST /empty":"","POST /object":{"value":"unsafe"}}'
        ),
    )

    assert load_capability_rules() == {"POST /valid": "risk.write"}


def test_authorization_uses_most_specific_matching_capability_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "true")
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        (
            '{"POST /analytics":"risk.analytics.write",'
            '"POST /analytics/risk/calculate":"risk.calculate.write"}'
        ),
    )
    headers = {
        "X-Actor-Id": "actor-1",
        "X-Tenant-Id": "tenant-1",
        "X-Role": "advisor",
        "X-Correlation-Id": "corr-1",
        "X-Service-Identity": "lotus-gateway",
        "X-Capabilities": "risk.analytics.write",
    }

    allowed, reason = authorize_write_request("POST", "/analytics/risk/calculate", headers)
    assert not allowed
    assert reason == "missing_capability:risk.calculate.write"

    headers["X-Capabilities"] = "risk.calculate.write"
    assert authorize_write_request("POST", "/analytics/risk/calculate", headers) == (True, None)


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
    assert body["correlation_id"] == "corr-413"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Enterprise-Policy-Version"] == "1.0.0"


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
    assert body["correlation_id"] == "corr-403"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Enterprise-Policy-Version"] == "1.0.0"


def test_enterprise_middleware_sets_policy_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "false")
    monkeypatch.setenv("ENTERPRISE_POLICY_VERSION", "2.0.0")
    client = TestClient(_enterprise_test_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Enterprise-Policy-Version"] == "2.0.0"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_enterprise_middleware_handles_invalid_numeric_env_and_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_AUTHZ", "false")
    monkeypatch.setenv("ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES", "not-an-int")
    client = TestClient(_enterprise_test_app())
    response = client.post("/writes", headers={"content-length": "not-an-int"}, content="ok")
    assert response.status_code == 200
