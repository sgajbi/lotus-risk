from __future__ import annotations

import sys
from pathlib import Path


def force_repo_src_first(project_root: Path) -> None:
    """Ensure gate scripts import this repo's app package in multi-repo workspaces."""
    src_path = str(project_root / "src")
    sys.path[:] = [path for path in sys.path if path != src_path]
    sys.path.insert(0, src_path)
