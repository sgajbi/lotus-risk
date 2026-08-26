from pathlib import Path

from scripts.clean_generated_artifacts import clean_generated_artifacts

import pytest

pytestmark = pytest.mark.governance


def test_clean_generated_artifacts_removes_only_allowlisted_byproducts(tmp_path: Path) -> None:
    generated_paths = [
        tmp_path / ".pytest_cache",
        tmp_path / ".mypy_cache",
        tmp_path / ".ruff_cache",
        tmp_path / ".import_linter_cache",
        tmp_path / "build",
        tmp_path / "dist",
        tmp_path / "htmlcov",
        tmp_path / "output",
        tmp_path / "src" / "lotus_risk.egg-info",
        tmp_path / "src" / "app" / "__pycache__",
        tmp_path / "tests" / "__pycache__",
    ]
    for path in generated_paths:
        path.mkdir(parents=True)
        (path / "artifact.txt").write_text("generated", encoding="utf-8")
    for path in [tmp_path / ".coverage", tmp_path / ".coverage.unit"]:
        path.write_text("coverage", encoding="utf-8")

    source_file = tmp_path / "src" / "app" / "main.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("source truth", encoding="utf-8")
    protected_file = tmp_path / ".git" / "__pycache__" / "artifact.pyc"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_text("protected", encoding="utf-8")

    removed = clean_generated_artifacts(tmp_path)

    assert all(not path.exists() for path in generated_paths)
    assert not (tmp_path / ".coverage").exists()
    assert not (tmp_path / ".coverage.unit").exists()
    assert source_file.exists()
    assert protected_file.exists()
    assert {path.name for path in removed} >= {"output", ".pytest_cache", "__pycache__"}


def test_clean_generated_artifacts_dry_run_reports_without_removing(tmp_path: Path) -> None:
    cache_dir = tmp_path / ".pytest_cache"
    cache_dir.mkdir()

    removed = clean_generated_artifacts(tmp_path, dry_run=True)

    assert removed == [cache_dir]
    assert cache_dir.exists()
