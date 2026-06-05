from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
READINESS_DOC = REPO_ROOT / "quality" / "final_pr_readiness.md"
OPENAPI_ARTIFACT_EVIDENCE_DOC = REPO_ROOT / "quality" / "openapi_artifact_evidence.md"


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

    required_terms = (
        "quality/quality_scorecard.md",
        "quality/openapi_artifact_evidence.md",
        "make openapi-artifact-gate",
        "output/openapi/lotus-risk.openapi.json",
        "make quality-baseline",
        "make security-audit",
        "Quality Baseline",
        "Remote Feature Lane",
        "Pull Request Merge Gate",
        "gateway-backed token-validation evidence",
        "production telemetry",
        "not a completion claim",
    )

    for term in required_terms:
        assert term in text


def test_openapi_artifact_evidence_manifest_records_attachment_metadata() -> None:
    text = OPENAPI_ARTIFACT_EVIDENCE_DOC.read_text(encoding="utf-8")

    required_terms = (
        "output/openapi/lotus-risk.openapi.json",
        "make openapi-artifact-gate",
        "make openapi-gate",
        "SHA-256",
        "Artifact size bytes",
        "Path count",
        "Operation count",
    )

    for term in required_terms:
        assert term in text
