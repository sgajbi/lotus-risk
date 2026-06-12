from pathlib import Path

from scripts.source_size_gate import find_source_size_violations, main


def test_source_size_gate_reports_only_files_above_limit(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "small.py").write_text("x = 1\n", encoding="utf-8")
    (source_root / "large.py").write_text("x = 1\n" * 4, encoding="utf-8")

    violations = find_source_size_violations(source_root, max_lines=3)

    assert [(item.path.name, item.lines) for item in violations] == [("large.py", 4)]


def test_source_size_gate_main_returns_failure_for_violation(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "large.py").write_text("x = 1\n" * 2, encoding="utf-8")

    assert main(["--source-root", str(source_root), "--max-lines", "1"]) == 1
    assert main(["--source-root", str(source_root), "--max-lines", "2"]) == 0
