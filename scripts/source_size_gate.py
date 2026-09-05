"""Reject source modules that exceed the governed maintainability limit.

A gate that inspects nothing must fail. Otherwise a renamed source root, a package restructure, or
an incorrect working directory looks indistinguishable from a clean tree.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT / "src"
DEFAULT_MAX_LINES = int(os.getenv("SOURCE_FILE_MAX_LINES", "450"))
DEFAULT_TEST_ROOT = ROOT / "tests"
#: Test modules carry their own budget, banked at today's largest module
#: (#254). It is a ratchet: it moves DOWN as oversized modules are split,
#: never up - the same discipline the source ceiling follows.
DEFAULT_TEST_MAX_LINES = int(os.getenv("TEST_FILE_MAX_LINES", "1044"))


@dataclass(frozen=True)
class SourceSizeViolation:
    path: Path
    lines: int


def find_source_size_violations(
    source_root: Path,
    *,
    max_lines: int,
) -> tuple[list[SourceSizeViolation], int]:
    """Return violations and the number of Python files actually inspected."""

    violations: list[SourceSizeViolation] = []
    inspected = 0
    for path in sorted(source_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        inspected += 1
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > max_lines:
            violations.append(SourceSizeViolation(path=path, lines=lines))
    return violations, inspected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--test-root", type=Path, default=DEFAULT_TEST_ROOT)
    parser.add_argument("--test-max-lines", type=int, default=DEFAULT_TEST_MAX_LINES)
    return parser


def _check_root(root: Path, *, max_lines: int, label: str) -> int:
    violations, inspected = find_source_size_violations(root, max_lines=max_lines)
    if inspected == 0:
        print(
            f"{label} size gate failed: inspected 0 files under {root}. "
            "A gate that inspected nothing cannot report success."
        )
        return 1
    if violations:
        print(f"{label} size gate failed: maximum {max_lines} lines per Python file.")
        for violation in violations:
            print(f"- {violation.path}: {violation.lines} lines")
        return 1
    print(
        f"{label} size gate passed: {inspected} files inspected, none exceeding {max_lines} lines."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_status = _check_root(args.source_root, max_lines=args.max_lines, label="Source")
    test_status = _check_root(args.test_root, max_lines=args.test_max_lines, label="Test")
    return source_status or test_status


if __name__ == "__main__":
    raise SystemExit(main())
