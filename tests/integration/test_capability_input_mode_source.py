"""A vocabulary-only mutation must reach the shipped operational route and filter."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = 'SupportedInputMode = Literal["stateless", "stateful", "simulation"]'
EXTENDED = 'SupportedInputMode = Literal["stateless", "stateful", "simulation", "future_mode"]'


def test_new_input_mode_requires_only_contract_alias_edit(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "src/app", tmp_path / "src/app")
    contract = tmp_path / "src/app/contracts/capabilities.py"
    source = contract.read_text(encoding="utf-8")
    assert source.count(ORIGINAL) == 1
    contract.write_text(source.replace(ORIGINAL, EXTENDED, 1), encoding="utf-8")

    probe = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
from app.main import app
from app.contracts.capabilities import CapabilityWorkflow, SUPPORTED_INPUT_MODES
from app.services.capability_workflows import aggregate_supported_input_modes

client = TestClient(app)
ops = client.get('/ops')
capabilities = client.get('/integration/capabilities')
assert ops.status_code == capabilities.status_code == 200
observed = CapabilityWorkflow(
    workflow_key='synthetic-mode-proof',
    endpoint_path='/analytics/risk/concentration',
    supported_input_modes=['future_mode'],
    support_status='full',
)
print(json.dumps({
    'inventory': list(SUPPORTED_INPUT_MODES),
    'ops': ops.json()['input_modes'],
    'filtered': aggregate_supported_input_modes([observed]),
    'implemented': capabilities.json()['supported_input_modes'],
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", probe, str(tmp_path / "src")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout.strip().splitlines()[-1])
    assert observed["inventory"] == ["stateless", "stateful", "simulation", "future_mode"]
    assert observed["ops"] == observed["inventory"]
    assert observed["filtered"] == ["future_mode"]
    assert observed["implemented"] == ["stateless", "stateful", "simulation"]
