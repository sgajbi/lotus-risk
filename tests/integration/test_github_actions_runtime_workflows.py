from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
MAKEFILE = REPO_ROOT / "Makefile"


def test_governed_workflows_enforce_node24_artifact_runtime_posture() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "check: github-actions-runtime-gate" in makefile
    assert "ci: github-actions-runtime-gate" in makefile
    assert (
        "github-actions-runtime-gate:\n\tpython scripts/validate_github_actions_runtime.py"
        in makefile
    )

    for workflow_name in ("pr-merge-gate.yml", "main-releasability.yml"):
        workflow = (WORKFLOW_DIR / workflow_name).read_text(encoding="utf-8")
        assert "run: make github-actions-runtime-gate" in workflow, workflow_name

    for workflow_name in (
        "image-release.yml",
        "main-releasability.yml",
        "pr-merge-gate.yml",
        "quality-baseline.yml",
    ):
        workflow = (WORKFLOW_DIR / workflow_name).read_text(encoding="utf-8")
        assert "actions/upload-artifact@v4" not in workflow, workflow_name
        assert "actions/download-artifact@v4" not in workflow, workflow_name
