"""Hold the shape of the *product's* test suite.

The pyramid is a claim about how product behaviour is covered: mostly fast unit tests, a
meaningful band of integration tests, a thin layer of end-to-end tests. Tests that assert about
the repository itself — its configuration, tooling, workflows, documentation, or test
infrastructure — are not product tests. Counting them distorts the shape and, worse, makes the
gate hostile to the very coverage it should encourage: every governance test added pushed the
unit bucket up and squeezed the integration and e2e ratios down, so a repository could be
blocked from asserting its own CI contracts. See issue #220.

Governance tests declare themselves with `pytest.mark.governance` and are deselected here. The
marker is the source of truth; `tests/unit/test_test_pyramid_gate.py` holds it honest by
asserting that every `tests/unit` module which never touches product code carries it.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Tests that assert about the repository rather than the product. Deselected from every bucket.
NON_PRODUCT_MARKER_EXPRESSION = "not governance"

# Decimal places used when reporting a ratio. Displayed values are rounded *away* from the bound
# they failed, so a failure message can never print a number that satisfies its own bound.
_DISPLAY_PRECISION = 4


@dataclass(frozen=True)
class BucketPolicy:
    name: str
    path: str
    min_ratio: float
    max_ratio: float


BUCKET_POLICIES = (
    BucketPolicy(name="unit", path="tests/unit", min_ratio=0.70, max_ratio=0.85),
    BucketPolicy(name="integration", path="tests/integration", min_ratio=0.15, max_ratio=0.25),
    BucketPolicy(name="e2e", path="tests/e2e", min_ratio=0.03, max_ratio=0.10),
)

# `--collect-only` reports "collected 712 items / 130 deselected / 582 selected" when a marker
# expression applies and "collected 26 items" when nothing is deselected. Reading the first number
# in the first form yields the pre-deselection total, which would silently defeat the marker.
_SELECTED = re.compile(r"(\d+)\s+selected")
_COLLECTED = re.compile(r"collected\s+(\d+)\s+items?")


def _collect_count(path: str) -> int:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            path,
            "-m",
            NON_PRODUCT_MARKER_EXPRESSION,
            "--collect-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    match = _SELECTED.search(output) or _COLLECTED.search(output)
    if completed.returncode != 0 or match is None:
        print(f"Failed to collect tests for {path}", file=sys.stderr)
        print(output, file=sys.stderr)
        raise SystemExit(1)
    return int(match.group(1))


def _rounded_away_from(percent: float, *, below_bound: bool) -> str:
    """Render `percent` so it never crosses the bound it failed.

    `f"{2.9954:.2f}"` is `3.00`, which passes the inclusive 3% floor it was reported as failing.
    A message that prints a value satisfying its own bound sends the reader to debug a comparison
    that is correct.
    """

    scale = 10**_DISPLAY_PRECISION
    rounded = math.floor(percent * scale) if below_bound else math.ceil(percent * scale)
    return f"{rounded / scale:.{_DISPLAY_PRECISION}f}"


def _failure_message(policy: BucketPolicy, count: int, total: int, percent: float) -> str:
    below = percent < policy.min_ratio * 100
    bound = policy.min_ratio if below else policy.max_ratio
    side = "below the" if below else "above the"
    limit = "floor" if below else "ceiling"
    required = (
        math.ceil(policy.min_ratio * total) if below else math.floor(policy.max_ratio * total)
    )
    direction = "at least" if below else "at most"
    return (
        f"test pyramid gate failed for {policy.name}: {count} of {total} product tests is "
        f"{_rounded_away_from(percent, below_bound=below)}%, {side} {bound * 100:.0f}% {limit}. "
        f"At this total the bucket needs {direction} {required} tests."
    )


def main() -> int:
    missing = [policy.path for policy in BUCKET_POLICIES if not (ROOT / policy.path).is_dir()]
    if missing:
        # A gate that inspected nothing must fail rather than report a vacuous pass.
        print(f"Configured test bucket paths are missing: {missing}", file=sys.stderr)
        return 1

    counts = {policy.name: _collect_count(policy.path) for policy in BUCKET_POLICIES}
    total = sum(counts.values())
    if total == 0:
        print("No product tests collected.", file=sys.stderr)
        return 1

    failed = False
    for policy in BUCKET_POLICIES:
        count = counts[policy.name]
        percent = count / total * 100
        print(
            f"{policy.name}: {count} product tests ({percent:.2f}%) "
            f"target {policy.min_ratio * 100:.0f}%..{policy.max_ratio * 100:.0f}%"
        )
        if not policy.min_ratio <= count / total <= policy.max_ratio:
            failed = True
            print(_failure_message(policy, count, total, percent), file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
