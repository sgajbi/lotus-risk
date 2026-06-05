from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_DOC = REPO_ROOT / "docs" / "security-deployment-policy.md"
THREAT_MODEL_DOC = REPO_ROOT / "docs" / "security-threat-model.md"
RUNBOOK_DOC = REPO_ROOT / "docs" / "runbooks" / "service-operations.md"
WIKI_SECURITY_DOC = REPO_ROOT / "wiki" / "Security-and-Governance.md"


def test_enterprise_deployment_policy_records_bank_mode_requirements() -> None:
    text = POLICY_DOC.read_text(encoding="utf-8")

    required_terms = (
        "Enterprise bank deployment",
        "ENTERPRISE_ENFORCE_AUTHZ=true",
        "ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true",
        "ENTERPRISE_PRIMARY_KEY_ID",
        "ENTERPRISE_SECRET_ROTATION_DAYS",
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        "ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES",
        "gateway",
        "token-validation evidence",
        "ASGI/server request body limits",
        "Content-Length",
    )

    for term in required_terms:
        assert term in text


def test_threat_model_uses_finalized_deployment_policy_language() -> None:
    text = THREAT_MODEL_DOC.read_text(encoding="utf-8")

    assert "security-deployment-policy.md" in text
    assert "Enterprise bank deployment mode requires `ENTERPRISE_ENFORCE_AUTHZ=true`" in text
    assert (
        "Promote final enterprise readiness mode once deployment identity validation is settled"
        not in text
    )
    assert (
        "server-level request body limits for requests without trustworthy `Content-Length`"
        not in text
    )


def test_runbook_and_wiki_link_enterprise_deployment_policy() -> None:
    runbook = RUNBOOK_DOC.read_text(encoding="utf-8")
    wiki_security = WIKI_SECURITY_DOC.read_text(encoding="utf-8")

    assert "docs/security-deployment-policy.md" in runbook
    assert "docs/security-deployment-policy.md" in wiki_security
    assert "ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true" in wiki_security
