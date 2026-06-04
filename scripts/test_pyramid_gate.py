from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class BucketPolicy:
    name: str
    min_ratio: float
    max_ratio: float


BUCKET_POLICIES = (
    BucketPolicy(name="unit", min_ratio=0.70, max_ratio=0.85),
    BucketPolicy(name="integration", min_ratio=0.15, max_ratio=0.25),
    BucketPolicy(name="e2e", min_ratio=0.03, max_ratio=0.10),
)


def _collect_count(path: str) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", path, "--collect-only"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"collected\s+(\d+)\s+items", output)
    if completed.returncode != 0 or match is None:
        print(f"Failed to collect tests for {path}", file=sys.stderr)
        print(output, file=sys.stderr)
        raise SystemExit(1)
    return int(match.group(1))


def main() -> int:
    counts = {
        "unit": _collect_count("tests/unit"),
        "integration": _collect_count("tests/integration"),
        "e2e": _collect_count("tests/e2e"),
    }
    total = sum(counts.values())
    if total == 0:
        print("No tests collected.", file=sys.stderr)
        return 1

    failed = False
    for policy in BUCKET_POLICIES:
        ratio = counts[policy.name] / total
        percent = ratio * 100
        min_percent = policy.min_ratio * 100
        max_percent = policy.max_ratio * 100
        print(
            f"{policy.name}: {counts[policy.name]} tests ({percent:.2f}%) "
            f"target {min_percent:.0f}%..{max_percent:.0f}%"
        )
        if ratio < policy.min_ratio or ratio > policy.max_ratio:
            failed = True
            print(
                f"test pyramid gate failed for {policy.name}: "
                f"{percent:.2f}% not in [{min_percent:.0f}%, {max_percent:.0f}%]",
                file=sys.stderr,
            )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
