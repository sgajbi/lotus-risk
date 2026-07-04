from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

PR_GRADE_TARGETS = {
    "lint",
    "check-deps",
    "architecture-gate",
    "no-alias-gate",
    "typecheck",
    "openapi-gate",
    "openapi-artifact-gate",
    "api-vocabulary-gate",
    "mesh-contract-validate",
    "complexity-gate",
    "source-size-gate",
    "dependency-hygiene-gate",
    "dead-code-gate",
    "migration-smoke",
    "test-pyramid-gate",
    "test-all",
    "security-audit",
    "docker-build",
}


def _make_target_dependencies(target: str) -> set[str]:
    text = MAKEFILE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(f"{target}:"):
            return set(line.split(":", maxsplit=1)[1].split())
    raise AssertionError(f"missing Makefile target: {target}")


def test_make_ci_is_pr_grade_local_gate() -> None:
    assert PR_GRADE_TARGETS <= _make_target_dependencies("ci")


def test_ci_local_is_documented_as_partial_split_suite_loop() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "Split-suite local coverage loop without Docker" in makefile
    assert "Use `make ci` for PR-grade parity" in makefile


def test_make_clean_delegates_to_cleanup_script() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "clean:" in makefile
    assert "python scripts/clean_generated_artifacts.py" in makefile


def test_governed_workflows_run_mesh_contract_validation() -> None:
    for workflow in (
        "feature-lane.yml",
        "pr-merge-gate.yml",
        "main-releasability.yml",
    ):
        text = (WORKFLOW_DIR / workflow).read_text(encoding="utf-8")
        assert "run: make mesh-contract-validate" in text, workflow
