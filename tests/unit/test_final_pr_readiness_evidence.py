from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


REPO_ROOT = Path(__file__).resolve().parents[2]
READINESS_DOC = REPO_ROOT / "quality" / "final_pr_readiness.md"
OPENAPI_ARTIFACT_EVIDENCE_DOC = REPO_ROOT / "quality" / "openapi_artifact_evidence.md"
FINAL_PR_BODY_DOC = REPO_ROOT / "quality" / "final_pr_body.md"
FINAL_REFACTOR_CLOSURE_AUDIT_DOC = REPO_ROOT / "quality" / "final_refactor_closure_audit.md"


def test_final_pr_readiness_pack_contains_required_pr_sections() -> None:
    text = READINESS_DOC.read_text(encoding="utf-8")

    required_headings = (
        "## Refactor Approach",
        "## Before And After Scorecard",
        "## Architecture Improvements",
        "## API And OpenAPI Improvements",
        "## Testing Improvements",
        "## Security Improvements",
        "## Observability Improvements",
        "## Documentation Improvements",
        "## Validation Evidence To Include In The PR",
        "## Known Limitations",
        "## Follow-Up Backlog",
        "## PR Assembly Checklist",
    )

    for heading in required_headings:
        assert heading in text


def test_final_pr_readiness_pack_pins_evidence_commands_and_risks() -> None:
    text = READINESS_DOC.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())

    required_terms = (
        "refactor/enterprise-risk-backend",
        "quality/quality_scorecard.md",
        "quality/openapi_artifact_evidence.md",
        "output/openapi/lotus-risk.openapi.evidence.json",
        "661",
        "112",
        "quality/baseline_report.md",
        "regenerated immediately before final PR assembly",
        "make openapi-artifact-gate",
        "output/openapi/lotus-risk.openapi.json",
        "make quality-baseline",
        "make security-audit",
        "Quality Baseline",
        "Remote Feature Lane",
        "Pull Request Merge Gate",
        "Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-risk",
        "Sync-RepoWikis.ps1 -Publish",
        "Operations-Runbook.md",
        "Security-and-Governance.md",
        "Supported-Features.md",
        "gateway-backed token-validation evidence",
        "production telemetry",
        "not a completion claim",
        "immutable audit record, not current PR evidence",
    )

    for term in required_terms:
        assert term in text or term in normalized_text


def test_current_readiness_docs_do_not_pin_stale_historical_metadata() -> None:
    current_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (READINESS_DOC, OPENAPI_ARTIFACT_EVIDENCE_DOC, FINAL_PR_BODY_DOC)
    )

    stale_terms = (
        "feat/enterprise-risk-refactor-continuation",
        "9FA31D518B37B95A4F73079A7393ADDF81A041F8BDA4309CA23D5D42598055F8",
        "`554` unit tests",
        "`103` Python test files",
        "Pull Request Merge Gate` passed on PR #149",
    )

    for term in stale_terms:
        assert term not in current_text


def test_openapi_artifact_evidence_contract_records_generated_manifest_boundary() -> None:
    text = OPENAPI_ARTIFACT_EVIDENCE_DOC.read_text(encoding="utf-8")

    required_terms = (
        "output/openapi/lotus-risk.openapi.json",
        "output/openapi/lotus-risk.openapi.evidence.json",
        "output/openapi/lotus-risk.openapi.evidence.md",
        "make openapi-artifact-gate",
        "make openapi-gate",
        "Git branch",
        "Git commit SHA",
        "Repository URL",
        "CI pipeline/run ID",
        "UTC generation timestamp",
        "Artifact size bytes",
        "Path count",
        "Operation count",
        "Artifact SHA-256",
        "Do not pin current branch names",
    )

    for term in required_terms:
        assert term in text


def test_final_pr_body_covers_enterprise_refactor_pr_requirements() -> None:
    text = FINAL_PR_BODY_DOC.read_text(encoding="utf-8")

    required_terms = (
        "# Summary",
        "# Why",
        "# Refactoring Approach",
        "# Before/After Scorecard",
        "# Architecture Improvements",
        "# API And OpenAPI Improvements",
        "# Testing Improvements",
        "# Security Improvements",
        "# Observability Improvements",
        "# Documentation Improvements",
        "# Dependency Changes And Justification",
        "# Behavior, Migration, And Configuration Notes",
        "# Validation Evidence",
        "# Known Limitations",
        "# Follow-Up Backlog",
        "# Review Focus Areas",
        "quality/quality_scorecard.md",
        "quality/openapi_artifact_evidence.md",
        "output/openapi/lotus-risk.openapi.evidence.json",
        "Known vulnerabilities: 0",
        "Pull Request Merge Gate",
        "Sync-RepoWikis.ps1 -Publish -Repository lotus-risk",
        "quality/final_refactor_closure_audit.md",
        "Historical post-merge closure evidence for PR #149",
    )

    for term in required_terms:
        assert term in text


def test_final_refactor_closure_audit_records_post_merge_definition_of_done() -> None:
    text = FINAL_REFACTOR_CLOSURE_AUDIT_DOC.read_text(encoding="utf-8")

    required_terms = (
        "historical audit record",
        "Do not use it as current PR readiness proof",
        "https://github.com/sgajbi/lotus-risk/pull/149",
        "e98ecaf56dd59979e53d7ce948b8e5827be523b9",
        "Definition Of Done Audit",
        "Pipeline Enforcement Audit",
        "Main Releasability Gate",
        "Quality Baseline",
        "Pull Request Merge Gate",
        "Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-risk",
        "DiffCount 0",
        "make openapi-gate",
        "make security-audit",
        "make test-pyramid-gate",
        "make docker-build",
        "gateway-backed token-validation evidence",
    )

    for term in required_terms:
        assert term in text
