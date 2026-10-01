from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ALEMBIC_DIR = Path("alembic")
VERSIONS_DIR = ALEMBIC_DIR / "versions"
REQUIRED_DOC = Path("docs/standards/migration-contract.md")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", "sqlite:///:memory:")
    return environment


def _run(command: list[str]) -> int:
    return subprocess.run(command, check=False, env=_environment()).returncode


def _has_one_head() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        check=False,
        capture_output=True,
        text=True,
        env=_environment(),
    )
    heads = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode == 0 and len(heads) == 1:
        return True
    print("Expected exactly one Alembic head, found:")
    for head in heads:
        print(f" - {head}")
    return False


def check_alembic_sql() -> int:
    if not ALEMBIC_DIR.exists() or not VERSIONS_DIR.exists():
        print("Missing Alembic migration directories.")
        return 1
    if not any(VERSIONS_DIR.glob("*.py")):
        print("No Alembic migration revision files found.")
        return 1
    if not REQUIRED_DOC.exists():
        print(f"Missing required migration contract document: {REQUIRED_DOC}")
        return 1
    if not _has_one_head():
        return 1
    if _run([sys.executable, "-m", "alembic", "history"]) != 0:
        return 1
    if _run([sys.executable, "-m", "alembic", "upgrade", "head", "--sql"]) != 0:
        return 1
    print("Migration contract check passed (alembic-sql mode).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the risk migration contract.")
    parser.add_argument("--mode", choices=["alembic-sql"], default="alembic-sql")
    parser.parse_args()
    return check_alembic_sql()


if __name__ == "__main__":
    raise SystemExit(main())
