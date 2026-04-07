from __future__ import annotations

import sys
from pathlib import Path

from scripts._repo_imports import force_repo_src_first


def test_force_repo_src_first_moves_repo_src_ahead_of_other_lotus_apps() -> None:
    original_path = list(sys.path)
    project_root = Path("C:/Users/Sandeep/projects/lotus-risk")
    repo_src = str(project_root / "src")
    other_repo_src = "C:/Users/Sandeep/projects/lotus-ai/src"

    try:
        sys.path[:] = [other_repo_src, repo_src, "C:/Python313/Lib/site-packages"]

        force_repo_src_first(project_root)

        assert sys.path[0] == repo_src
        assert sys.path[1] == other_repo_src
        assert sys.path.count(repo_src) == 1
    finally:
        sys.path[:] = original_path
