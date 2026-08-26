from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


REPO_ROOT = Path(__file__).resolve().parents[2]
THREAT_MODEL_DOC = REPO_ROOT / "docs" / "security-threat-model.md"
SECURITY_DOC = REPO_ROOT / "docs" / "security.md"


def test_security_threat_model_records_current_abuse_controls() -> None:
    text = THREAT_MODEL_DOC.read_text(encoding="utf-8")

    required_terms = (
        "ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES",
        "ENTERPRISE_INGRESS_MAX_BODY_BYTES",
        "ENTERPRISE_ASGI_MAX_BODY_BYTES",
        "ENTERPRISE_TRUSTED_INGRESS_SECRET",
        "X-Lotus-Trusted-Ingress",
        "413 PAYLOAD_TOO_LARGE",
        "ENTERPRISE_ENFORCE_AUTHZ=true",
        "X-Actor-Id",
        "X-Tenant-Id",
        "X-Role",
        "X-Correlation-Id",
        "missing_service_identity",
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        "redact_sensitive",
        "app.upstream_errors",
        "bounded-label rule",
        "make security-audit",
        "scripts/dependency_health_check.py --skip-outdated",
        "security-deployment-policy.md",
        "Enterprise bank deployment mode requires",
        "ASGI/server request body limits",
        "machine-readable proof",
        "credential-bearing downstream URL",
        "docs/configuration.md",
        "fails application construction",
        "missing_capability_rule",
        "test_enterprise_middleware_requires_trusted_ingress_before_write_authz",
        "test_enterprise_middleware_protects_operator_endpoints_with_trusted_ingress",
    )

    for term in required_terms:
        assert term in text


def test_security_overview_links_threat_model() -> None:
    assert "security-threat-model.md" in SECURITY_DOC.read_text(encoding="utf-8")
