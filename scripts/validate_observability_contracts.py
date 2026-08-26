from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SRC_STR = str(SRC)
while SRC_STR in sys.path:
    sys.path.remove(SRC_STR)
sys.path.insert(0, SRC_STR)

from app import observability
from app.integrations.upstream_operations import UPSTREAM_OPERATION_VALUES

LOCAL_OBSERVABILITY_DIR = ROOT / "contracts" / "observability"
CONTRACT_PATH = LOCAL_OBSERVABILITY_DIR / "lotus-risk-monitoring.v1.json"
DOMAIN_OBSERVABILITY_DOC_PATH = ROOT / "docs" / "domain-apis" / "risk-observability.md"

_FORBIDDEN_LABEL_HINTS = {
    "account",
    "actor",
    "client",
    "correlation",
    "idempotency",
    "raw_error",
    "request_hash",
    "run_id",
    "instrument_id",
}


def implemented_metric_contract() -> dict[str, tuple[str, ...]]:
    return {
        f"{observability.ENDPOINT_EXECUTIONS_TOTAL._name}_total": tuple(
            observability.ENDPOINT_EXECUTIONS_TOTAL._labelnames
        ),
        observability.ENDPOINT_EXECUTION_SECONDS._name: tuple(
            observability.ENDPOINT_EXECUTION_SECONDS._labelnames
        ),
        f"{observability.UPSTREAM_REQUESTS_TOTAL._name}_total": tuple(
            observability.UPSTREAM_REQUESTS_TOTAL._labelnames
        ),
        observability.UPSTREAM_REQUEST_SECONDS._name: tuple(
            observability.UPSTREAM_REQUEST_SECONDS._labelnames
        ),
        f"{observability.CALCULATION_SUPPORTABILITY_TOTAL._name}_total": tuple(
            observability.CALCULATION_SUPPORTABILITY_TOTAL._labelnames
        ),
        f"{observability.ANALYTICS_FRESHNESS_BUCKET_TOTAL._name}_total": tuple(
            observability.ANALYTICS_FRESHNESS_BUCKET_TOTAL._labelnames
        ),
        f"{observability.HTTP_REQUESTS_TOTAL._name}_total": tuple(
            observability.HTTP_REQUESTS_TOTAL._labelnames
        ),
    }


def _load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        # This is invalid contract content after successful JSON parsing, so ValueError is exact.
        raise ValueError("Observability contract root must be an object.")  # noqa: TRY004
    return payload


def _markdown_slug(heading: str) -> str:
    slug = heading.strip().lower()
    slug = re.sub(r"[^a-z0-9 -]", "", slug)
    return re.sub(r"\s+", "-", slug)


def _validate_runbook_reference(runbook: str) -> list[str]:
    path_text, _, anchor = runbook.partition("#")
    runbook_path = ROOT / path_text
    if not runbook_path.exists():
        return [f"{runbook}: alert runbook file does not exist"]
    if not anchor:
        return []
    headings = {
        _markdown_slug(line.lstrip("#").strip())
        for line in runbook_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }
    if anchor not in headings:
        return [f"{runbook}: alert runbook anchor does not exist"]
    return []


def _validate_metric(
    *,
    metric: dict[str, Any],
    implemented_metrics: dict[str, tuple[str, ...]],
) -> list[str]:
    issues: list[str] = []
    name = metric.get("name")
    if name not in implemented_metrics:
        issues.append(f"{name}: metric is not implemented by app.observability")
        return issues

    labels = metric.get("labels")
    if not isinstance(labels, dict):
        issues.append(f"{name}: labels must be an object")
        return issues

    declared_label_names = tuple(labels)
    expected_label_names = implemented_metrics[name]
    if declared_label_names != expected_label_names:
        issues.append(
            f"{name}: labels {declared_label_names} do not match implementation "
            f"{expected_label_names}"
        )

    for label_name, allowed_values in labels.items():
        if any(hint in label_name.lower() for hint in _FORBIDDEN_LABEL_HINTS):
            issues.append(f"{name}.{label_name}: sensitive label name is forbidden")
        if not isinstance(allowed_values, list) or not allowed_values:
            issues.append(f"{name}.{label_name}: allowed values must be a non-empty list")
            continue
        for value in allowed_values:
            if not isinstance(value, str) or not value:
                issues.append(f"{name}.{label_name}: allowed values must be non-empty strings")
            elif any(hint in value.lower() for hint in _FORBIDDEN_LABEL_HINTS):
                issues.append(f"{name}.{label_name}: sensitive label value {value!r} is forbidden")
    return issues


def _declared_metric(payload: dict[str, Any], metric_name: str) -> dict[str, Any] | None:
    metrics = payload.get("metrics")
    if not isinstance(metrics, list):
        return None
    for metric in metrics:
        if isinstance(metric, dict) and metric.get("name") == metric_name:
            return metric
    return None


def _validate_upstream_operation_value(value: str) -> list[str]:
    issues: list[str] = []
    if "?" in value or "#" in value:
        issues.append(f"{value!r}: operation values must not include query strings or fragments")

    concrete_identifier_patterns = (
        r"/calc-[^/]+",
        r"/SIM[_-][^/]+",
        r"/PB[_-][^/]+",
        r"currency=",
    )
    for pattern in concrete_identifier_patterns:
        if re.search(pattern, value, flags=re.IGNORECASE):
            issues.append(f"{value!r}: operation value appears to include concrete runtime data")
            break
    return issues


def _validate_upstream_operation_contract(payload: dict[str, Any]) -> list[str]:
    metric_name = "lotus_risk_upstream_requests_total"
    metric = _declared_metric(payload, metric_name)
    if metric is None:
        return [f"{metric_name}: metric is missing from contract"]

    labels = metric.get("labels")
    if not isinstance(labels, dict):
        return [f"{metric_name}: labels must be an object"]

    operations = labels.get("operation")
    if not isinstance(operations, list):
        return [f"{metric_name}.operation: operation allowlist must be a list"]

    declared_operations = {value for value in operations if isinstance(value, str)}
    expected_operations = set(UPSTREAM_OPERATION_VALUES)
    issues: list[str] = []

    missing = sorted(expected_operations - declared_operations)
    if missing:
        issues.append(f"{metric_name}.operation: missing runtime operation values {missing}")

    extra = sorted(declared_operations - expected_operations)
    if extra:
        issues.append(
            f"{metric_name}.operation: contract declares values not owned by runtime "
            f"vocabulary {extra}"
        )

    for value in sorted(declared_operations):
        issues.extend(
            f"{metric_name}.operation {issue}"
            for issue in _validate_upstream_operation_value(value)
        )
    return issues


def _contract_metric_values(payload: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    metric_values: dict[str, dict[str, list[str]]] = {}
    metrics = payload.get("metrics")
    if not isinstance(metrics, list):
        return metric_values
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        metric_name = metric.get("name")
        labels = metric.get("labels")
        if not isinstance(metric_name, str) or not isinstance(labels, dict):
            continue
        metric_values[metric_name] = {
            label_name: [value for value in values if isinstance(value, str)]
            for label_name, values in labels.items()
            if isinstance(label_name, str) and isinstance(values, list)
        }
    return metric_values


def _validate_domain_observability_doc(
    payload: dict[str, Any],
    doc_path: Path = DOMAIN_OBSERVABILITY_DOC_PATH,
) -> list[str]:
    if not doc_path.exists():
        return [f"{doc_path}: domain API observability doc does not exist"]

    text = doc_path.read_text(encoding="utf-8")
    metric_values = _contract_metric_values(payload)
    issues: list[str] = []

    for metric_name, labels in metric_values.items():
        if metric_name not in text:
            issues.append(f"{doc_path}: missing metric {metric_name}")
        for label_name, allowed_values in labels.items():
            if label_name not in text:
                issues.append(f"{doc_path}: missing label {metric_name}.{label_name}")
            for value in allowed_values:
                if value not in text:
                    issues.append(
                        f"{doc_path}: missing allowed value {metric_name}.{label_name}={value}"
                    )

    for required_text in (
        "lotus-risk-http-5xx",
        "docs/runbooks/service-operations.md#http-5xx-alert",
        "docs/runbooks/service-operations.md#endpoint-failure-rate-alert",
        "docs/runbooks/service-operations.md#calculation-supportability-alert",
    ):
        if required_text not in text:
            issues.append(f"{doc_path}: missing required operator reference {required_text!r}")

    return issues


def validate_observability_contract(
    path: Path = CONTRACT_PATH,
    domain_doc_path: Path = DOMAIN_OBSERVABILITY_DOC_PATH,
) -> list[str]:
    if not path.exists():
        return [f"{path}: observability monitoring contract does not exist"]

    payload = _load_contract(path)
    issues: list[str] = []
    implemented_metrics = implemented_metric_contract()
    declared_metrics = payload.get("metrics")
    if not isinstance(declared_metrics, list) or not declared_metrics:
        return [f"{path}: metrics must be a non-empty list"]

    declared_metric_names = set()
    for metric in declared_metrics:
        if not isinstance(metric, dict):
            issues.append(f"{path}: metric entries must be objects")
            continue
        declared_metric_names.add(metric.get("name"))
        issues.extend(_validate_metric(metric=metric, implemented_metrics=implemented_metrics))

    for implemented_metric in implemented_metrics:
        if implemented_metric not in declared_metric_names:
            issues.append(f"{implemented_metric}: implemented metric is missing from contract")

    issues.extend(_validate_upstream_operation_contract(payload))
    issues.extend(_validate_domain_observability_doc(payload, domain_doc_path))

    dashboards = payload.get("dashboards")
    if not isinstance(dashboards, list) or not dashboards:
        issues.append(f"{path}: dashboards must be a non-empty list")
        dashboards = []

    for dashboard in dashboards:
        for panel in dashboard.get("panels", []):
            metric_name = panel.get("metric")
            if metric_name not in declared_metric_names:
                issues.append(f"{panel.get('panel_id')}: dashboard panel references {metric_name}")

    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        issues.append(f"{path}: alerts must be a non-empty list")
        alerts = []

    for alert in alerts:
        metric_name = alert.get("metric")
        if metric_name not in declared_metric_names:
            issues.append(f"{alert.get('alert_id')}: alert references {metric_name}")
        if alert.get("severity") not in {"info", "warning", "critical"}:
            issues.append(f"{alert.get('alert_id')}: alert severity is not governed")
        runbook = alert.get("runbook")
        if not runbook:
            issues.append(f"{alert.get('alert_id')}: alert runbook is required")
        elif isinstance(runbook, str):
            issues.extend(_validate_runbook_reference(runbook))
        else:
            issues.append(f"{alert.get('alert_id')}: alert runbook must be a string")

    return issues


def main() -> int:
    issues = validate_observability_contract()
    if issues:
        for issue in issues:
            print(issue)
        return 1

    print(f"Validated observability monitoring contract at {CONTRACT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
