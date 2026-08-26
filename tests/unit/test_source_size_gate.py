from pathlib import Path

import pytest

from scripts.source_size_gate import find_source_size_violations, main

pytestmark = pytest.mark.governance


def test_source_size_gate_reports_only_files_above_limit(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "small.py").write_text("x = 1\n", encoding="utf-8")
    (source_root / "large.py").write_text("x = 1\n" * 4, encoding="utf-8")

    violations, inspected = find_source_size_violations(source_root, max_lines=3)

    assert inspected == 2
    assert [(item.path.name, item.lines) for item in violations] == [("large.py", 4)]


def test_source_size_gate_main_returns_failure_for_violation(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "large.py").write_text("x = 1\n" * 2, encoding="utf-8")

    assert main(["--source-root", str(source_root), "--max-lines", "1"]) == 1
    assert main(["--source-root", str(source_root), "--max-lines", "2"]) == 0


@pytest.mark.parametrize("root_kind", ["empty", "absent"])
def test_source_size_gate_fails_when_it_inspects_no_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    root_kind: str,
) -> None:
    source_root = tmp_path / root_kind
    if root_kind == "empty":
        source_root.mkdir()

    exit_code = main(["--source-root", str(source_root), "--max-lines", "450"])

    assert exit_code == 1
    assert f"inspected 0 files under {source_root}" in capsys.readouterr().out


def test_source_size_gate_success_reports_the_inspected_file_count(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "one.py").write_text("x = 1\n", encoding="utf-8")
    (source_root / "two.py").write_text("y = 2\n", encoding="utf-8")

    exit_code = main(["--source-root", str(source_root), "--max-lines", "3"])

    assert exit_code == 0
    assert "2 files inspected, none exceeding 3 lines" in capsys.readouterr().out
