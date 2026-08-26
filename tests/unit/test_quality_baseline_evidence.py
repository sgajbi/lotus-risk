from pathlib import Path
from typing import Any

import pytest

from scripts import generate_quality_baseline

pytestmark = pytest.mark.governance


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_REPORT = REPO_ROOT / "quality" / "baseline_report.md"
REVIEW_LEDGER = REPO_ROOT / "docs" / "architecture" / "CODEBASE-REVIEW-LEDGER.md"
REVIEW_PLAYBOOK = REPO_ROOT / "docs" / "architecture" / "CODEBASE-REVIEW-PLAYBOOK.md"
SECURITY_FINDINGS = REPO_ROOT / "quality" / "security_findings.md"
REFACTOR_DECISIONS = REPO_ROOT / "quality" / "refactor_decisions.md"
QUALITY_SCORECARD = REPO_ROOT / "quality" / "quality_scorecard.md"


def test_git_value_returns_unknown_when_git_command_fails(monkeypatch: Any) -> None:
    monkeypatch.setattr(generate_quality_baseline, "_run", lambda _command: (1, ""))

    assert generate_quality_baseline.git_value("rev-parse", "HEAD") == "unknown"


def test_generated_baseline_separates_immutable_before_evidence_from_current_state() -> None:
    text = BASELINE_REPORT.read_text(encoding="utf-8")
    source_hotspots = text.split("### Largest Source Files", maxsplit=1)[1].split(
        "### Largest Functions And Classes", maxsplit=1
    )[0]

    assert "# Lotus Risk Enterprise Refactor Current-State Baseline" in text
    assert "immutable initial baseline is commit `3254774`" in text
    assert "## Generation Identity" in text
    assert "Process-local downstream composition now lives in `src/app/runtime`" in text
    assert "RuntimeDownstreamClients" in text
    assert "tests/" not in source_hotspots


def test_refactor_control_documents_record_required_operational_evidence() -> None:
    required_documents = (REVIEW_LEDGER, REVIEW_PLAYBOOK, SECURITY_FINDINGS, REFACTOR_DECISIONS)

    for document in required_documents:
        assert document.exists()
        assert document.read_text(encoding="utf-8").strip()

    ledger = REVIEW_LEDGER.read_text(encoding="utf-8")
    assert "RISK-REF-001" in ledger
    assert "Quality measurement and CI truthfulness" in ledger


def test_generated_scorecard_preserves_resilience_and_performance_evidence() -> None:
    scorecard = QUALITY_SCORECARD.read_text(encoding="utf-8")

    assert "| Resilience and performance |" in scorecard
    assert "FastAPI lifespan owns reusable dependency-specific HTTP pools" in scorecard


def test_generated_scorecard_preserves_security_hardening_evidence() -> None:
    scorecard = QUALITY_SCORECARD.read_text(encoding="utf-8")

    assert "downstream base URLs are hardened with negative tests" in scorecard
    assert "trusted-ingress proof and protected operator endpoints" in scorecard
    assert "typed `src/app/runtime` downstream composition boundary" in scorecard
    assert "enterprise runtime and unmapped writes fail closed" in scorecard


def test_generated_scorecard_preserves_problem_details_evidence() -> None:
    baseline = BASELINE_REPORT.read_text(encoding="utf-8")
    scorecard = QUALITY_SCORECARD.read_text(encoding="utf-8")

    assert "additive RFC 7807/problem-details" in baseline
    assert (
        "standard error examples are builder-backed and include additive "
        "RFC 7807/problem-details fields"
    ) in scorecard
