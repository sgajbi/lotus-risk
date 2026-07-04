from __future__ import annotations

import json
from pathlib import Path

from scripts.export_openapi_artifact import (
    REQUIRED_SPECTRAL_RULES,
    validate_openapi_artifact,
    validate_spectral_policy_config,
    write_openapi_artifact,
)


def _valid_schema() -> dict[str, object]:
    return {
        "openapi": "3.1.0",
        "paths": {
            "/analytics/risk/calculate": {
                "post": {
                    "operationId": "calculateRiskAnalytics",
                    "summary": "Calculate risk analytics",
                    "description": "Calculates risk analytics for a governed portfolio request.",
                    "tags": ["Risk Analytics"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "examples": {
                                    "stateful": {
                                        "summary": "Stateful request",
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
                        "service_identity_headers": [
                            "Authorization",
                            "X-Service-Identity",
                        ],
                        "trusted_ingress_header": "X-Lotus-Trusted-Ingress",
                        "capabilities_header": "X-Capabilities",
                        "capability_rules_env": "ENTERPRISE_CAPABILITY_RULES_JSON",
                        "denial_code": "AUTHORIZATION_DENIED",
                        "denial_reason": "authorization_policy_denied",
                    },
                }
            }
        },
    }


def test_spectral_policy_config_keeps_required_rules() -> None:
    errors = validate_spectral_policy_config()

    assert errors == []
    assert "operation-operationId: error" in REQUIRED_SPECTRAL_RULES
    assert "lotus-standard-error-responses:" in REQUIRED_SPECTRAL_RULES


def test_openapi_artifact_gate_rejects_missing_artifact(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.openapi.json"

    errors = validate_openapi_artifact(missing_path)

    assert errors == [f"{missing_path}: generated OpenAPI artifact is missing"]


def test_openapi_artifact_gate_validates_exported_schema(tmp_path: Path) -> None:
    artifact_path = tmp_path / "lotus-risk.openapi.json"
    write_openapi_artifact(_valid_schema(), artifact_path)

    errors = validate_openapi_artifact(artifact_path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert errors == []
    assert payload["paths"]["/analytics/risk/calculate"]["post"]["operationId"] == (
        "calculateRiskAnalytics"
    )
