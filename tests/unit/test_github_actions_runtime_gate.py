from __future__ import annotations

from pathlib import Path

from scripts.validate_github_actions_runtime import validate_workflows


def _write_workflow(path: Path, action_ref: str) -> None:
    path.write_text(
        "\n".join(
            [
                "name: sample",
                "jobs:",
                "  sample:",
                "    runs-on: ubuntu-latest",
                "    steps:",
                "      - uses: actions/checkout@v6",
                f"      - uses: {action_ref}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_github_actions_runtime_gate_accepts_node24_artifact_minimums(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    _write_workflow(workflows_dir / "upload.yml", "actions/upload-artifact@v6")
    _write_workflow(workflows_dir / "download.yml", "actions/download-artifact@v7")

    assert validate_workflows(workflows_dir) == []


def test_github_actions_runtime_gate_rejects_node20_artifact_majors(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    _write_workflow(workflows_dir / "upload.yml", "actions/upload-artifact@v4")
    _write_workflow(workflows_dir / "download.yml", "actions/download-artifact@v6")

    violations = validate_workflows(workflows_dir)

    assert [violation.slug for violation in violations] == [
        "actions/download-artifact",
        "actions/upload-artifact",
    ]
    assert [violation.minimum_major for violation in violations] == [7, 6]


def test_github_actions_runtime_gate_rejects_unparseable_and_quoted_refs(tmp_path: Path) -> None:
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    _write_workflow(workflows_dir / "unpinned.yml", "actions/upload-artifact@main")
    _write_workflow(workflows_dir / "quoted.yml", '"actions/download-artifact@v6"')

    violations = validate_workflows(workflows_dir)

    assert [violation.slug for violation in violations] == [
        "actions/download-artifact",
        "actions/upload-artifact",
    ]
    assert [violation.ref for violation in violations] == ["v6", "main"]
