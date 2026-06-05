from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
THREAT_MODEL_DOC = REPO_ROOT / "docs" / "security-threat-model.md"
SECURITY_DOC = REPO_ROOT / "docs" / "security.md"


def test_security_threat_model_records_current_abuse_controls() -> None:
    text = THREAT_MODEL_DOC.read_text(encoding="utf-8")

    required_terms = (
        "ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES",
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
    )

    for term in required_terms:
        assert term in text


def test_security_overview_links_threat_model() -> None:
    assert "security-threat-model.md" in SECURITY_DOC.read_text(encoding="utf-8")
