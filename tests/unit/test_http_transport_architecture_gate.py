"""Mutation proofs for the service-to-HTTP transport import boundary."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.governance


def _run_gate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "architecture-gate"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_http_transport_architecture_gate_rejects_mutation_and_missing_source(
    tmp_path: Path,
) -> None:
    shutil.copy2(ROOT / ".importlinter", tmp_path / ".importlinter")
    shutil.copy2(ROOT / "Makefile", tmp_path / "Makefile")
    shutil.copytree(ROOT / "src", tmp_path / "src")

    baseline = _run_gate(tmp_path)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr

    service = tmp_path / "src/app/services/attribution_group_evidence.py"
    service.write_text(
        service.read_text(encoding="utf-8").replace(
            "from __future__ import annotations",
            "from __future__ import annotations\nimport httpx",
            1,
        ),
        encoding="utf-8",
    )
    mutation = _run_gate(tmp_path)
    assert mutation.returncode != 0
    assert "Calculation services do not depend on HTTP transport BROKEN" in mutation.stdout

    missing_root = tmp_path / "missing_source"
    missing_root.mkdir()
    shutil.copy2(ROOT / ".importlinter", missing_root / ".importlinter")
    shutil.copy2(ROOT / "Makefile", missing_root / "Makefile")
    missing_source = _run_gate(missing_root)
    assert missing_source.returncode != 0
    assert "absent or empty" in missing_source.stdout + missing_source.stderr

    (missing_root / "src/app").mkdir(parents=True)
    empty_source = _run_gate(missing_root)
    assert empty_source.returncode != 0
    assert "absent or empty" in empty_source.stdout + empty_source.stderr
