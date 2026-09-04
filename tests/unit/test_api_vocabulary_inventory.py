from __future__ import annotations

from typing import Any, cast

import pytest

from scripts.api_vocabulary_inventory import build_inventory, validate_inventory

pytestmark = pytest.mark.governance


def _endpoint(inventory: dict[str, Any], *, method: str, path: str) -> dict[str, Any]:
    for endpoint in inventory["endpoints"]:
        if endpoint["method"] == method and endpoint["path"] == path:
            return cast(dict[str, Any], endpoint)
    raise AssertionError(f"missing endpoint {method} {path}")


def _field_semantic_id(endpoint: dict[str, Any], *, section: str, name: str) -> str:
    for field in endpoint[section]["fields"]:
        if field["name"] == name:
            return str(field["semanticId"])
    raise AssertionError(f"missing {section} field {name}")


def test_api_vocabulary_disambiguates_status_state_reason_and_type_fields() -> None:
    inventory = build_inventory()

    health = _endpoint(inventory, method="GET", path="/health")
    readiness = _endpoint(inventory, method="GET", path="/health/ready")
    ops = _endpoint(inventory, method="GET", path="/ops")
    trust = _endpoint(inventory, method="GET", path="/ops/trust-telemetry")
    risk = _endpoint(inventory, method="POST", path="/analytics/risk/calculate")
    mandate = _endpoint(inventory, method="POST", path="/analytics/risk/mandate-health-context")

    assert _field_semantic_id(health, section="response", name="status") == "lotus.health_status"
    assert (
        _field_semantic_id(readiness, section="response", name="status") == "lotus.readiness_status"
    )
    assert (
        _field_semantic_id(readiness, section="response", name="dependencies[].status")
        == "lotus.dependency_runtime_status"
    )
    assert _field_semantic_id(ops, section="response", name="status") == "lotus.ops_status"
    assert (
        _field_semantic_id(
            trust,
            section="response",
            name="products[].dependency_signals[].status",
        )
        == "lotus.trust_dependency_status"
    )
    assert _field_semantic_id(mandate, section="request", name="period.type") == "lotus.period_type"
    assert (
        _field_semantic_id(
            risk,
            section="response",
            name="metadata.risk_free_context.reason",
        )
        == "lotus.risk_free_context_reason"
    )
    assert (
        _field_semantic_id(
            risk,
            section="response",
            name="metadata.calculation_supportability.state",
        )
        == "lotus.calculation_supportability_state"
    )
    assert (
        _field_semantic_id(
            risk,
            section="response",
            name="metadata.calculation_supportability.reason",
        )
        == "lotus.calculation_supportability_reason"
    )


def test_api_vocabulary_keeps_the_two_unit_maps_contextually_distinct() -> None:
    """The rolling and attribution unit maps cover different metric vocabularies
    and value fields: a generator change collapsing both back to one generic ID
    would merge two incompatible unit contracts and the inventory would keep
    whichever description it met first."""

    inventory = build_inventory()

    rolling = _endpoint(inventory, method="POST", path="/analytics/risk/rolling-metrics")
    attribution = _endpoint(inventory, method="POST", path="/analytics/risk/historical-attribution")

    assert (
        _field_semantic_id(rolling, section="response", name="metadata.metric_unit_semantics")
        == "lotus.rolling_metric_unit_semantics"
    )
    assert (
        _field_semantic_id(attribution, section="response", name="metadata.metric_unit_semantics")
        == "lotus.attribution_metric_unit_semantics"
    )


def test_api_vocabulary_rejects_ambiguous_generic_semantic_id_collisions() -> None:
    inventory = {
        "attributeCatalog": [
            {
                "semanticId": "lotus.status",
                "canonicalTerm": "status",
                "preferredName": "status",
                "description": "Ambiguous status.",
                "example": "ok",
                "fieldPaths": ["status", "dependencies[].status"],
            }
        ],
        "endpoints": [],
    }

    errors = validate_inventory(inventory)

    assert any(
        "ambiguous semanticId lotus.status spans multiple field paths" in error for error in errors
    )


def test_api_vocabulary_allows_governed_shared_product_identity_paths() -> None:
    inventory = {
        "attributeCatalog": [
            {
                "semanticId": "lotus.product_name",
                "canonicalTerm": "product_name",
                "preferredName": "product_name",
                "description": "Source-owned product name.",
                "example": "RiskMetricsReport",
                "fieldPaths": ["metadata.product_name", "product_name"],
            }
        ],
        "endpoints": [],
    }

    assert validate_inventory(inventory) == []
