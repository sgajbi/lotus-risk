"""Contract tests for the scheduled online GitHub Action reference resolver."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.resolve_github_action_references import (
    ActionReference,
    ApiResponse,
    collect_references,
    overall_outcome,
    resolve_references,
)


class StubClient:
    def __init__(self, responses: dict[str, ApiResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, path: str) -> ApiResponse:
        self.calls.append(path)
        return self.responses[path]


def _reference(ref: str = "v6") -> ActionReference:
    return ActionReference("actions/checkout", ref, ".github/workflows/example.yml", 5)


def test_a_well_formed_but_nonexistent_tag_is_missing() -> None:
    references = [_reference("v9.99.0")]
    client = StubClient(
        {
            "repos/actions/checkout": ApiResponse(200),
            "repos/actions/checkout/git/ref/tags/v9.99.0": ApiResponse(404, detail="HTTP 404"),
        }
    )

    resolutions = resolve_references(references, client)

    assert resolutions[0].status == "missing_ref"
    assert overall_outcome(references, resolutions) == "missing"


def test_an_absent_or_inaccessible_repository_is_inconclusive() -> None:
    references = [_reference()]
    resolutions = resolve_references(
        references, StubClient({"repos/actions/checkout": ApiResponse(404, detail="HTTP 404")})
    )

    assert resolutions[0].status == "inconclusive"
    assert overall_outcome(references, resolutions) == "inconclusive"


def test_rate_limiting_is_inconclusive_not_green_or_missing() -> None:
    references = [_reference()]
    resolutions = resolve_references(
        references,
        StubClient(
            {"repos/actions/checkout": ApiResponse(403, detail="HTTP 403; rate-limit remaining=0")}
        ),
    )

    assert resolutions[0].status == "inconclusive"
    assert overall_outcome(references, resolutions) == "inconclusive"


def test_an_empty_scan_is_missing_not_a_vacuous_success() -> None:
    assert overall_outcome([], []) == "missing"


def test_cli_fails_when_the_workflow_inventory_is_empty(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    report = tmp_path / "report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "resolve_github_action_references.py"),
            "--workflows-dir",
            str(workflows),
            "--report",
            str(report),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={"GITHUB_TOKEN": "not-used-for-an-empty-inventory"},
    )

    assert completed.returncode == 1
    assert json.loads(report.read_text(encoding="utf-8"))["outcome"] == "missing"


def test_full_commit_sha_uses_the_commit_resolution_endpoint() -> None:
    sha = "a" * 40
    references = [_reference(sha)]
    resolutions = resolve_references(
        references,
        StubClient(
            {
                "repos/actions/checkout": ApiResponse(200),
                f"repos/actions/checkout/commits/{sha}": ApiResponse(200, {"sha": sha}),
            }
        ),
    )

    assert resolutions[0].status == "resolved"
    assert resolutions[0].resolved_sha == sha
    assert overall_outcome(references, resolutions) == "resolved"


def test_repository_existence_is_queried_once_for_multiple_references() -> None:
    references = [_reference("v5"), _reference("v6")]
    client = StubClient(
        {
            "repos/actions/checkout": ApiResponse(200),
            "repos/actions/checkout/git/ref/tags/v5": ApiResponse(
                200, {"object": {"type": "commit", "sha": "5" * 40}}
            ),
            "repos/actions/checkout/git/ref/tags/v6": ApiResponse(
                200, {"object": {"type": "commit", "sha": "6" * 40}}
            ),
        }
    )

    resolve_references(references, client)

    assert client.calls.count("repos/actions/checkout") == 1


def test_the_real_workflow_inventory_is_nonempty_and_includes_the_resolver() -> None:
    references = collect_references(ROOT / ".github" / "workflows")

    assert len(references) >= 10
    assert any(item.path.endswith("action-reference-resolution.yml") for item in references)
    assert any(item.slug == "github/codeql-action" and item.ref == "v4" for item in references)


def test_action_subpaths_are_collected_under_the_base_repository(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        "steps:\n  - uses: github/codeql-action/upload-sarif@v4\n", encoding="utf-8"
    )

    references = collect_references(tmp_path)

    assert [(item.slug, item.ref) for item in references] == [("github/codeql-action", "v4")]


def test_annotated_tags_are_peeled_to_the_commit_sha() -> None:
    commit_sha = "c" * 40
    tag_sha = "d" * 40
    client = StubClient(
        {
            "repos/actions/checkout": ApiResponse(200),
            "repos/actions/checkout/git/ref/tags/v6": ApiResponse(
                200, {"object": {"type": "tag", "sha": tag_sha}}
            ),
            f"repos/actions/checkout/git/tags/{tag_sha}": ApiResponse(
                200, {"object": {"type": "commit", "sha": commit_sha}}
            ),
        }
    )

    resolution = resolve_references([_reference()], client)[0]

    assert resolution.status == "resolved"
    assert resolution.resolved_sha == commit_sha


def test_cli_without_a_token_is_explicitly_inconclusive(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "one.yml").write_text("steps:\n  - uses: actions/checkout@v6\n", encoding="utf-8")
    report = tmp_path / "report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "resolve_github_action_references.py"),
            "--workflows-dir",
            str(workflows),
            "--report",
            str(report),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={},
    )

    assert completed.returncode == 2
    assert "GITHUB_TOKEN is required" in completed.stderr
    assert not report.exists()


def test_workflow_schedules_daily_resolution_and_cancels_inconclusive_runs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "action-reference-resolution.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "17 2 * * *"' in workflow
    assert "actions: write" in workflow
    assert "steps.resolver.outputs.outcome == 'missing'" in workflow
    assert "steps.resolver.outputs.outcome == 'inconclusive'" in workflow
    assert "/actions/runs/${GITHUB_RUN_ID}/cancel" in workflow
    assert "while true; do sleep 5; done" in workflow


def test_report_schema_records_counts_and_resolution_statuses(tmp_path: Path) -> None:
    from scripts.resolve_github_action_references import _write_report

    references = [_reference()]
    resolutions = resolve_references(
        references,
        StubClient(
            {
                "repos/actions/checkout": ApiResponse(200),
                "repos/actions/checkout/git/ref/tags/v6": ApiResponse(
                    200, {"object": {"type": "commit", "sha": "6" * 40}}
                ),
            }
        ),
    )
    report = tmp_path / "report.json"

    assert _write_report(report, references, resolutions) == "resolved"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["reference_occurrence_count"] == 1
    assert payload["unique_reference_count"] == 1
    assert payload["resolutions"][0]["status"] == "resolved"
    assert payload["resolutions"][0]["resolved_sha"] == "6" * 40
