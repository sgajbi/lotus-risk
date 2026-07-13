from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.validate_observability_contracts import validate_observability_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_CONTRACT = REPO_ROOT / "contracts" / "observability" / "lotus-risk-monitoring.v1.json"
DOMAIN_OBSERVABILITY_DOC = REPO_ROOT / "docs" / "domain-apis" / "risk-observability.md"
OBSERVABILITY_DOC = REPO_ROOT / "docs" / "observability.md"
SERVICE_RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "service-operations.md"


def _contract() -> dict[str, Any]:
    payload = json.loads(OBSERVABILITY_CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_contract(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _upstream_operation_values(payload: dict[str, Any]) -> list[str]:
    for metric in payload["metrics"]:
        if metric["name"] == "lotus_risk_upstream_requests_total":
            operations = metric["labels"]["operation"]
            assert isinstance(operations, list)
            return operations
    raise AssertionError("missing upstream metric")


def test_observability_contract_declares_dashboard_and_alert_evidence() -> None:
    payload = _contract()

    dashboard_ids = {dashboard["dashboard_id"] for dashboard in payload["dashboards"]}
    panel_ids = {
        panel["panel_id"] for dashboard in payload["dashboards"] for panel in dashboard["panels"]
    }
    alert_ids = {alert["alert_id"] for alert in payload["alerts"]}

    assert "lotus-risk-observability-overview" in dashboard_ids
    assert {
        "risk-endpoint-latency",
        "risk-upstream-latency",
    } <= panel_ids
    assert {
        "lotus-risk-endpoint-failure-rate",
        "lotus-risk-upstream-dependency-failures",
        "lotus-risk-calculation-supportability-degraded",
        "lotus-risk-http-5xx",
    } <= alert_ids


def test_supportability_alert_covers_operationally_bad_states() -> None:
    payload = _contract()
    alert = next(
        alert
        for alert in payload["alerts"]
        if alert["alert_id"] == "lotus-risk-calculation-supportability-degraded"
    )

    for state in (
        "degraded",
        "error",
        "permission_blocked",
        "unavailable",
        "blocked",
    ):
        assert state in alert["query"]


def test_observability_contract_alerts_reference_runbook_anchors() -> None:
    issues = validate_observability_contract(OBSERVABILITY_CONTRACT)

    assert issues == []


def test_domain_observability_doc_projects_monitoring_contract_labels() -> None:
    issues = validate_observability_contract(OBSERVABILITY_CONTRACT)

    assert issues == []


def test_domain_observability_doc_fails_on_missing_contract_value(tmp_path: Path) -> None:
    payload = _contract()
    for metric in payload["metrics"]:
        if metric["name"] == "lotus_risk_endpoint_executions_total":
            metric["labels"]["endpoint"].append("new-risk-product")
            break
    contract_path = tmp_path / "monitoring.json"
    _write_contract(contract_path, payload)

    issues = validate_observability_contract(contract_path, DOMAIN_OBSERVABILITY_DOC)

    assert any(
        "lotus_risk_endpoint_executions_total.endpoint=new-risk-product" in issue
        for issue in issues
    )


def test_observability_contract_requires_all_runtime_upstream_operations(
    tmp_path: Path,
) -> None:
    payload = _contract()
    operations = _upstream_operation_values(payload)
    operations.remove("/integration/reference/risk-free-series/coverage")
    contract_path = tmp_path / "monitoring.json"
    _write_contract(contract_path, payload)

    issues = validate_observability_contract(contract_path)

    assert any(
        "missing runtime operation values" in issue
        and "/integration/reference/risk-free-series/coverage" in issue
        for issue in issues
    )


def test_observability_contract_rejects_unbounded_upstream_operations(
    tmp_path: Path,
) -> None:
    payload = _contract()
    operations = _upstream_operation_values(payload)
    operations.append("/integration/reference/risk-free-series/coverage?currency=USD")
    operations.append("/integration/returns/series/results/calc-1")
    contract_path = tmp_path / "monitoring.json"
    _write_contract(contract_path, payload)

    issues = validate_observability_contract(contract_path)

    assert any("query strings or fragments" in issue for issue in issues)
    assert any("concrete runtime data" in issue for issue in issues)


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
