from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.validate_observability_contracts import validate_observability_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_CONTRACT = REPO_ROOT / "contracts" / "observability" / "lotus-risk-monitoring.v1.json"
OBSERVABILITY_DOC = REPO_ROOT / "docs" / "observability.md"
SERVICE_RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "service-operations.md"


def _contract() -> dict[str, Any]:
    payload = json.loads(OBSERVABILITY_CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_observability_contract_declares_dashboard_and_alert_evidence() -> None:
    payload = _contract()

    dashboard_ids = {dashboard["dashboard_id"] for dashboard in payload["dashboards"]}
    alert_ids = {alert["alert_id"] for alert in payload["alerts"]}

    assert "lotus-risk-observability-overview" in dashboard_ids
    assert {
        "lotus-risk-endpoint-failure-rate",
        "lotus-risk-upstream-dependency-failures",
        "lotus-risk-calculation-supportability-degraded",
        "lotus-risk-http-5xx",
    } <= alert_ids


def test_observability_contract_alerts_reference_runbook_anchors() -> None:
    issues = validate_observability_contract(OBSERVABILITY_CONTRACT)

    assert issues == []


def test_observability_docs_link_contract_and_alert_validation() -> None:
    observability_text = OBSERVABILITY_DOC.read_text(encoding="utf-8")
    runbook_text = SERVICE_RUNBOOK.read_text(encoding="utf-8")

    required_observability_terms = (
        "contracts/observability/lotus-risk-monitoring.v1.json",
        "alert definitions for endpoint failures",
        "make observability-contract-validate",
    )
    for term in required_observability_terms:
        assert term in observability_text

    required_runbook_anchors = (
        "## Endpoint Failure Rate Alert",
        "## Upstream Dependency Failure Alert",
        "## Calculation Supportability Alert",
        "## HTTP 5xx Alert",
    )
    for heading in required_runbook_anchors:
        assert heading in runbook_text
