"""Remove known local/generated artifacts without touching source truth."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROTECTED_NAMES = {".git", ".venv", "node_modules"}
ROOT_ARTIFACTS = {
    ".coverage",
    ".coverage.unit",
    ".coverage.integration",
    ".coverage.e2e",
    ".import_linter_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".benchmarks",
    "build",
    "dist",
    "htmlcov",
    "output",
}


def _is_protected(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return True
    return any(part in PROTECTED_NAMES for part in relative_parts)


def _remove_path(path: Path, *, root: Path, dry_run: bool) -> bool:
    if not path.exists() or _is_protected(path, root):
        return False
    if dry_run:
        return True
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def clean_generated_artifacts(root: Path = REPO_ROOT, *, dry_run: bool = False) -> list[Path]:
    """Remove allowlisted local artifacts and return removed paths."""

    removed: list[Path] = []
    for name in sorted(ROOT_ARTIFACTS):
        path = root / name
        if _remove_path(path, root=root, dry_run=dry_run):
            removed.append(path)

    for path in sorted(root.rglob("*.egg-info")):
        if _remove_path(path, root=root, dry_run=dry_run):
            removed.append(path)

    for pattern in (".coverage.*",):
        for path in sorted(root.glob(pattern)):
            if _remove_path(path, root=root, dry_run=dry_run):
                removed.append(path)

    for path in sorted(root.rglob("__pycache__")):
        if _remove_path(path, root=root, dry_run=dry_run):
            removed.append(path)

    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    removed = clean_generated_artifacts(args.root, dry_run=args.dry_run)
    for path in removed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
