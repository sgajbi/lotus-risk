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
    assert "Measured source/test SHA-256" in text
    assert "## Validation Transcript" in text
    assert "Process-local downstream composition now lives in `src/app/runtime`" in text
    assert "RuntimeDownstreamClients" in text
    assert "tests/" not in source_hotspots


def test_source_test_fingerprint_tracks_inputs_not_branch_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src" / "app" / "example.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    tests = tmp_path / "tests" / "unit" / "test_example.py"
    tests.parent.mkdir(parents=True)
    tests.write_text("def test_value(): pass\n", encoding="utf-8")
    monkeypatch.setattr(generate_quality_baseline, "ROOT", tmp_path)
    monkeypatch.setattr(generate_quality_baseline, "SRC_DIR", tmp_path / "src")
    monkeypatch.setattr(generate_quality_baseline, "TESTS_DIR", tmp_path / "tests")
    first = generate_quality_baseline.source_test_fingerprint()
    (tmp_path / "branch-metadata.txt").write_text("different branch\n", encoding="utf-8")
    assert generate_quality_baseline.source_test_fingerprint() == first
    source.write_bytes(b"VALUE = 1\r\n")
    assert generate_quality_baseline.source_test_fingerprint() == first
    source.write_text("VALUE = 2\n", encoding="utf-8")
    assert generate_quality_baseline.source_test_fingerprint() != first


def test_file_size_measurement_counts_normalized_utf8_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src" / "app" / "example.py"
    source.parent.mkdir(parents=True)
    source.write_bytes("VALUE = 'é'\r\n".encode())
    tests = tmp_path / "tests"
    tests.mkdir()
    monkeypatch.setattr(generate_quality_baseline, "ROOT", tmp_path)
    monkeypatch.setattr(generate_quality_baseline, "SRC_DIR", tmp_path / "src")
    monkeypatch.setattr(generate_quality_baseline, "TESTS_DIR", tests)
    assert generate_quality_baseline.collect_file_sizes() == [
        generate_quality_baseline.FileSize(
            path="src/app/example.py", lines=1, bytes=len("VALUE = 'é'\n".encode())
        )
    ]


def test_quality_check_accepts_fresh_reports_and_rejects_stale_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    committed = tmp_path / "quality"
    committed.mkdir()
    for name in generate_quality_baseline.REPORT_NAMES:
        (committed / name).write_text("current\n", encoding="utf-8")

    def generate(_files: object, _symbols: object, _unit_count: str) -> None:
        for name in generate_quality_baseline.REPORT_NAMES:
            (generate_quality_baseline.QUALITY_DIR / name).write_text("current\n", encoding="utf-8")

    monkeypatch.setattr(generate_quality_baseline, "QUALITY_DIR", committed)
    monkeypatch.setattr(generate_quality_baseline, "collect_file_sizes", list)
    monkeypatch.setattr(generate_quality_baseline, "collect_symbol_sizes", list)
    monkeypatch.setattr(generate_quality_baseline, "collect_unit_test_count", lambda: ("1", ""))
    monkeypatch.setattr(generate_quality_baseline, "_generate_reports", generate)
    assert generate_quality_baseline.main(["--check"]) == 0
    assert not capsys.readouterr().err

    stale = committed / "baseline_report.md"
    stale.write_text("stale\n", encoding="utf-8")
    assert generate_quality_baseline.main(["--check"]) == 1
    assert "baseline_report.md" in capsys.readouterr().err
    assert stale.read_text(encoding="utf-8") == "stale\n"

    def incomplete(_files: object, _symbols: object, _unit_count: str) -> None:
        for name in generate_quality_baseline.REPORT_NAMES - {"baseline_report.md"}:
            (generate_quality_baseline.QUALITY_DIR / name).write_text("current\n", encoding="utf-8")

    monkeypatch.setattr(generate_quality_baseline, "_generate_reports", incomplete)
    assert generate_quality_baseline.main(["--check"]) == 1
    assert "quality generator targets changed" in capsys.readouterr().err

    missing_dir = tmp_path / "missing-quality"
    monkeypatch.setattr(generate_quality_baseline, "QUALITY_DIR", missing_dir)
    monkeypatch.setattr(generate_quality_baseline, "_generate_reports", generate)
    assert generate_quality_baseline.main(["--check"]) == 1
    assert not missing_dir.exists()


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
