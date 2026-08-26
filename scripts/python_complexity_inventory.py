"""Inventory cyclomatic complexity and fail when it regresses.

`complexity-gate` used to be two `radon` report commands. Neither `radon cc` nor `radon mi` accepts
a failure threshold - `-n C` filters what is *printed*, not what fails - so both exited 0 whatever
the tree contained, while sitting in the blocking `ci` lane beside three gates that do fail. See
issue #225.

This parses `radon`'s JSON output and applies explicit thresholds, following
`lotus-performance/scripts/python_complexity_inventory.py` rather than inventing a variant.

One deliberate difference from that reference: it treats an empty result set as a maximum of 0 and
passes. A scan that inspected nothing is indistinguishable from a clean tree there, so a renamed
source root or a lane running from the wrong directory would report success. Here, collecting no
blocks is a failure - see `lotus-platform#738`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = ("src",)
HIGH_COMPLEXITY_RANKS = frozenset({"D", "E", "F"})


@dataclass(frozen=True)
class ComplexityFinding:
    path: str
    name: str
    kind: str
    rank: str
    complexity: int
    line: int


def _run_radon(paths: Sequence[str]) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "radon", "cc", *paths, "-s", "-j"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


def parse_complexity_payload(payload: dict[str, object]) -> list[ComplexityFinding]:
    findings: list[ComplexityFinding] = []
    for raw_path, entries in payload.items():
        if not isinstance(entries, list):
            # radon reports a per-file syntax error as a mapping with an "error" key. Skipping it
            # silently would let an unparseable file reduce the measured maximum.
            raise RuntimeError(f"radon could not analyse {raw_path}: {entries}")
        path = raw_path.replace("\\", "/")
        for entry in entries:
            findings.append(
                ComplexityFinding(
                    path=path,
                    name=str(entry.get("name", "")),
                    kind=str(entry.get("type", "")),
                    rank=str(entry.get("rank", "")),
                    complexity=int(entry.get("complexity", 0)),
                    line=int(entry.get("lineno", 0)),
                )
            )
    findings.sort(key=lambda finding: (-finding.complexity, finding.path, finding.line))
    return findings


def collect_complexity(paths: Sequence[str] = DEFAULT_PATHS) -> list[ComplexityFinding]:
    return parse_complexity_payload(json.loads(_run_radon(paths)))


def rank_count(findings: Sequence[ComplexityFinding], ranks: frozenset[str]) -> int:
    return sum(1 for finding in findings if finding.rank in ranks)


def complexity_gate_failures(
    findings: Sequence[ComplexityFinding],
    *,
    max_cc: int | None,
    max_high_complexity: int | None,
) -> list[str]:
    """Threshold breaches, plus the zero-input case.

    A gate that inspected nothing must fail. Reporting a maximum of 0 for an empty scan makes an
    absent source root look like the cleanest possible tree, which is the direction that hides a
    defect rather than surfacing one.
    """

    failures: list[str] = []

    if not findings:
        failures.append(
            "no code blocks were inspected - an empty scan is not a clean tree. Check the scanned "
            "paths and the working directory."
        )
        return failures

    observed_max_cc = findings[0].complexity
    if max_cc is not None and observed_max_cc > max_cc:
        worst = findings[0]
        failures.append(
            f"max cyclomatic complexity {observed_max_cc} exceeds allowed {max_cc} "
            f"({worst.path}:{worst.line} {worst.name})"
        )

    observed_high = rank_count(findings, HIGH_COMPLEXITY_RANKS)
    if max_high_complexity is not None and observed_high > max_high_complexity:
        failures.append(
            f"high-complexity (rank D-F) block count {observed_high} exceeds allowed "
            f"{max_high_complexity}"
        )

    return failures


def render_report(findings: Sequence[ComplexityFinding], *, limit: int) -> str:
    if not findings:
        return "No code blocks inspected."
    ranks = sorted({finding.rank for finding in findings})
    counts = ", ".join(f"{rank}={rank_count(findings, frozenset({rank}))}" for rank in ranks)
    lines = [
        f"Inspected {len(findings)} blocks; ranks {counts}; max cyclomatic complexity "
        f"{findings[0].complexity}.",
        "",
    ]
    lines.extend(
        f"  {finding.rank} {finding.complexity:>3}  {finding.path}:{finding.line} {finding.name}"
        for finding in findings[:limit]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory Python cyclomatic complexity")
    parser.add_argument("--path", action="append", dest="paths")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--max-cc", type=int, help="Fail when observed max complexity exceeds this")
    parser.add_argument(
        "--max-high-complexity", type=int, help="Fail when rank D-F block count exceeds this"
    )
    args = parser.parse_args(argv)

    findings = collect_complexity(tuple(args.paths or DEFAULT_PATHS))
    print(render_report(findings, limit=args.limit))

    failures = complexity_gate_failures(
        findings, max_cc=args.max_cc, max_high_complexity=args.max_high_complexity
    )
    if failures:
        print("\nComplexity gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
