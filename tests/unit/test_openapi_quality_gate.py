from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT_PATH = str(PROJECT_ROOT)
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_PATH)

from scripts.openapi_quality_gate import evaluate_schema  # noqa: E402

pytestmark = pytest.mark.governance


def _operation(**overrides: object) -> dict[str, object]:
    operation: dict[str, object] = {
        "operationId": "calculateRiskAnalytics",
        "summary": "Calculate risk analytics",
        "description": "Calculates risk analytics for a governed portfolio request.",
        "tags": ["Risk Analytics"],
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "stateful": {
                            "summary": "Stateful portfolio request",
                            "value": {"portfolioId": "PB_SG_GLOBAL_BAL_001"},
                        }
                    }
                }
            }
        },
        "responses": {
            "200": {"description": "Risk analytics response"},
            "403": {"description": "Authorization denied"},
            "422": {"description": "Validation error"},
        },
        "x-lotus-enterprise-authorization": {
            "required_context_headers": ["X-Actor-Id"],
            "service_identity_headers": ["Authorization", "X-Service-Identity"],
            "trusted_ingress_header": "X-Lotus-Trusted-Ingress",
            "capabilities_header": "X-Capabilities",
            "capability_rules_env": "ENTERPRISE_CAPABILITY_RULES_JSON",
            "denial_code": "AUTHORIZATION_DENIED",
            "denial_reason": "authorization_policy_denied",
        },
    }
    operation.update(overrides)
    return operation


def _schema(operation: dict[str, object]) -> dict[str, object]:
    return {"paths": {"/analytics/risk/calculate": {"post": operation}}}


def test_openapi_quality_gate_rejects_missing_operation_id() -> None:
    operation = _operation()
    operation.pop("operationId")

    errors = evaluate_schema(_schema(operation), service_name="lotus-risk")

    assert any("POST /analytics/risk/calculate: missing operationId" in error for error in errors)


def test_openapi_quality_gate_rejects_missing_json_request_examples() -> None:
    operation = _operation(
        requestBody={
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/RiskAnalyticsRequest"}
                }
            }
        }
    )

    errors = evaluate_schema(_schema(operation), service_name="lotus-risk")

    assert any(
        "POST /analytics/risk/calculate: missing JSON request example" in error for error in errors
    )


def test_openapi_quality_gate_accepts_documented_json_mutation_operation() -> None:
    errors = evaluate_schema(_schema(_operation()), service_name="lotus-risk")

    assert errors == []


def test_openapi_quality_gate_rejects_missing_enterprise_authz_extension() -> None:
    operation = _operation()
    operation.pop("x-lotus-enterprise-authorization")

    errors = evaluate_schema(_schema(operation), service_name="lotus-risk")

    assert any(
        (
            "POST /analytics/risk/calculate: missing enterprise authorization "
            "caller-context extension"
        )
        in error
        for error in errors
    )
