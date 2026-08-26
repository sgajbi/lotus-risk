from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


def test_pr_auto_merge_workflow_uses_rebase_strategy() -> None:
    workflow = Path(".github/workflows/pr-auto-merge.yml").read_text(encoding="utf-8")

    assert "gh pr merge" in workflow
    assert "--auto --rebase --delete-branch" in workflow
    assert "--auto --merge --delete-branch" not in workflow


WORKFLOW_ROOT = Path(".github/workflows")
GATEWAY_REFERENCE_NOTE = (
    "lotus-gateway is the reference implementation; divergence here reintroduces the ungated-main "
    "defect recorded in issue #216."
)


def test_auto_merge_uses_a_token_that_can_trigger_downstream_workflows() -> None:
    """GITHUB_TOKEN pushes do not trigger workflow runs.

    Under `github.token`, an automated merge pushes to `main` without triggering
    `main-releasability.yml`, so the commit lands ungated. This repository's tip `39514f39` is
    bot-committed and its only gate run came from `workflow_dispatch` (#216).
    """

    workflow = (WORKFLOW_ROOT / "pr-auto-merge.yml").read_text(encoding="utf-8")

    assert "secrets.LOTUS_AUTOMERGE_TOKEN" in workflow, GATEWAY_REFERENCE_NOTE
    assert "GH_TOKEN: ${{ github.token }}" not in workflow, GATEWAY_REFERENCE_NOTE


def test_auto_merge_fails_visibly_when_the_token_is_absent() -> None:
    workflow = (WORKFLOW_ROOT / "pr-auto-merge.yml").read_text(encoding="utf-8")

    assert 'if [ -z "$GH_TOKEN" ]; then' in workflow
    assert "::warning::LOTUS_AUTOMERGE_TOKEN is required" in workflow


def test_auto_merge_requests_no_more_permission_than_it_needs() -> None:
    workflow = (WORKFLOW_ROOT / "pr-auto-merge.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read\n" in workflow
    assert "contents: write" not in workflow
    assert "timeout-minutes:" in workflow


def test_protected_branch_skip_handling_is_preserved() -> None:
    """This repository handles a case the reference does not; adopting the token fix must keep it."""

    workflow = (WORKFLOW_ROOT / "pr-auto-merge.yml").read_text(encoding="utf-8")

    assert "Protected branch rules not configured" in workflow


def test_a_dispatcher_exists_so_the_gate_does_not_depend_on_the_push_trigger() -> None:
    dispatcher_path = WORKFLOW_ROOT / "merged-pr-main-releasability.yml"

    assert dispatcher_path.is_file(), (
        "merged-pr-main-releasability.yml is the fallback that runs the gate when the merge push "
        "does not trigger it. " + GATEWAY_REFERENCE_NOTE
    )
    dispatcher = dispatcher_path.read_text(encoding="utf-8")
    assert "types: [closed]" in dispatcher
    assert "pull_request.merged == true" in dispatcher
    assert "gh workflow run main-releasability.yml" in dispatcher
    assert "expected_sha" in dispatcher


def test_main_releasability_validates_the_exact_dispatched_revision() -> None:
    workflow = (WORKFLOW_ROOT / "main-releasability.yml").read_text(encoding="utf-8")

    assert "expected_sha:" in workflow
    assert "exact-revision-assertion:" in workflow
    assert "does not match expected merged PR SHA" in workflow
    assert workflow.count("needs: [exact-revision-assertion]") >= 2


def test_main_releasability_is_dispatch_only() -> None:
    """A suppressed push trigger is silent; a failed dispatch is a visible failed run."""

    workflow = (WORKFLOW_ROOT / "main-releasability.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert 'branches: [ "main" ]' not in workflow


def test_main_releasability_concurrency_is_keyed_per_commit_not_per_branch() -> None:
    """A branch-keyed group lets a second merge cancel the first commit's in-flight gate.

    With `cancel-in-progress: true` and a group keyed on `github.ref`, every gate run on `main`
    shares one group. Two merges close together leave the earlier commit with a *cancelled* run —
    not passed, not failed — and nothing reports that. Keyed on `github.sha`, each commit gets its
    own group and cannot be cancelled by a later one.
    """

    workflow = (WORKFLOW_ROOT / "main-releasability.yml").read_text(encoding="utf-8")

    assert "group: ${{ github.workflow }}-${{ github.sha }}" in workflow
    assert "group: ${{ github.workflow }}-${{ github.ref }}" not in workflow
