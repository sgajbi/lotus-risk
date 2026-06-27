from __future__ import annotations

from pathlib import Path


def test_pr_auto_merge_workflow_uses_rebase_strategy() -> None:
    workflow = Path(".github/workflows/pr-auto-merge.yml").read_text(encoding="utf-8")

    assert "gh pr merge" in workflow
    assert "--auto --rebase --delete-branch" in workflow
    assert "--auto --merge --delete-branch" not in workflow
