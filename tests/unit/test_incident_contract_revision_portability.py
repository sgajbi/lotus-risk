import json
from pathlib import Path

import pytest

from scripts.validate_incident_response_contract import _incident_contract_revision_sha256

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts" / "observability" / "lotus-risk-incident-response.v1.json"
MONITORING_PATH = REPO_ROOT / "contracts" / "observability" / "lotus-risk-monitoring.v1.json"


def test_contract_revision_is_independent_of_monitoring_json_serialization(
    tmp_path: Path,
) -> None:
    monitoring = json.loads(MONITORING_PATH.read_text(encoding="utf-8"))
    lf_path = tmp_path / "monitoring-lf.json"
    crlf_path = tmp_path / "monitoring-crlf.json"
    lf_path.write_bytes((json.dumps(monitoring, indent=2) + "\n").encode())
    crlf_serialized = json.dumps(monitoring, indent=4, sort_keys=True)
    crlf_path.write_bytes((crlf_serialized.replace("\n", "\r\n") + "\r\n").encode())
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    lf_revision = _incident_contract_revision_sha256(contract, monitoring_path=lf_path)
    crlf_revision = _incident_contract_revision_sha256(contract, monitoring_path=crlf_path)

    assert lf_revision == crlf_revision

    monitoring["purpose"] = "Semantically changed monitoring policy."
    crlf_path.write_bytes(
        (json.dumps(monitoring, indent=2).replace("\n", "\r\n") + "\r\n").encode()
    )
    assert _incident_contract_revision_sha256(contract, monitoring_path=crlf_path) != lf_revision
