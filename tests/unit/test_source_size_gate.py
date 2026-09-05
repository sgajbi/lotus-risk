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

    test_args = ["--test-root", str(source_root), "--test-max-lines", "2"]
    assert main(["--source-root", str(source_root), "--max-lines", "1", *test_args]) == 1
    assert main(["--source-root", str(source_root), "--max-lines", "2", *test_args]) == 0


@pytest.mark.parametrize("root_kind", ["empty", "absent"])
def test_source_size_gate_fails_when_it_inspects_no_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    root_kind: str,
) -> None:
    source_root = tmp_path / root_kind
    if root_kind == "empty":
        source_root.mkdir()

    exit_code = main(
        ["--source-root", str(source_root), "--max-lines", "450", "--test-root", str(source_root)]
    )

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

    exit_code = main(
        [
            "--source-root",
            str(source_root),
            "--max-lines",
            "3",
            "--test-root",
            str(source_root),
            "--test-max-lines",
            "3",
        ]
    )

    assert exit_code == 0
    assert "2 files inspected, none exceeding 3 lines" in capsys.readouterr().out


def test_the_gate_budgets_test_modules_under_their_own_ceiling(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test modules carry their own banked ceiling (#254): a source tree
    within budget does not excuse an oversized test module, and the failure
    names the test root explicitly."""

    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "small.py").write_text("x = 1\n", encoding="utf-8")
    test_root = tmp_path / "tests"
    test_root.mkdir()
    (test_root / "test_big.py").write_text("y = 2\n" * 5, encoding="utf-8")

    exit_code = main(
        [
            "--source-root",
            str(source_root),
            "--max-lines",
            "10",
            "--test-root",
            str(test_root),
            "--test-max-lines",
            "4",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Source size gate passed" in output
    assert "Test size gate failed" in output
    assert "test_big.py: 5 lines" in output


def test_an_empty_test_root_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "small.py").write_text("x = 1\n", encoding="utf-8")
    test_root = tmp_path / "tests"
    test_root.mkdir()

    exit_code = main(
        [
            "--source-root",
            str(source_root),
            "--max-lines",
            "10",
            "--test-root",
            str(test_root),
        ]
    )

    assert exit_code == 1
    assert f"inspected 0 files under {test_root}" in capsys.readouterr().out
