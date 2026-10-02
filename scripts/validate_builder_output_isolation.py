"""Prove untrusted package build code cannot suppress output-collision validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

FIXTURE = Path("tests/fixtures/malicious-build-backend")
EXPECTED_REFUSAL = "Builder output replaces protected runtime executable"


def main() -> int:
    result = subprocess.run(
        [
            "docker",
            "build",
            "--progress=plain",
            "--no-cache",
            "--file",
            str(FIXTURE / "Dockerfile"),
            str(FIXTURE),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    if result.returncode == 0:
        raise SystemExit("malicious package build unexpectedly passed output validation")
    if EXPECTED_REFUSAL not in output:
        raise SystemExit(
            "malicious package build failed without the expected collision refusal\n" + output
        )
    print("builder-output isolation proof passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
