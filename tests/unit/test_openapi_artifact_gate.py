from __future__ import annotations

import json
from pathlib import Path

from scripts.export_openapi_artifact import (
    REQUIRED_SPECTRAL_RULES,
    build_openapi_evidence,
    validate_openapi_artifact,
    validate_openapi_evidence,
    validate_spectral_policy_config,
    write_openapi_evidence,
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


def test_openapi_artifact_evidence_records_current_source_identity(tmp_path: Path) -> None:
    artifact_path = tmp_path / "lotus-risk.openapi.json"
    evidence_json_path = tmp_path / "lotus-risk.openapi.evidence.json"
    evidence_markdown_path = tmp_path / "lotus-risk.openapi.evidence.md"
    schema = _valid_schema()
    write_openapi_artifact(schema, artifact_path)

    evidence = build_openapi_evidence(
        schema,
        artifact_path,
        generated_at_utc="2026-07-05T00:00:00Z",
        source_identity={
            "git_branch": "refactor/enterprise-risk-backend",
            "git_commit_sha": "abc123",
            "repo_url": "https://github.com/sgajbi/lotus-risk",
            "ci_pipeline_run_id": "local",
        },
    )
    write_openapi_evidence(
        evidence,
        json_path=evidence_json_path,
        markdown_path=evidence_markdown_path,
    )

    errors = validate_openapi_evidence(
        evidence,
        schema,
        artifact_path,
        source_identity={
            "git_branch": "refactor/enterprise-risk-backend",
            "git_commit_sha": "abc123",
            "repo_url": "https://github.com/sgajbi/lotus-risk",
            "ci_pipeline_run_id": "local",
        },
    )
    manifest_text = evidence_markdown_path.read_text(encoding="utf-8")

    assert errors == []
    assert evidence_json_path.exists()
    assert "`refactor/enterprise-risk-backend`" in manifest_text
    assert "`abc123`" in manifest_text
    assert evidence["artifact"]["size_bytes"] == artifact_path.stat().st_size
    assert evidence["artifact"]["sha256"]
    assert evidence["openapi"]["path_count"] == 1
    assert evidence["openapi"]["operation_count"] == 1


def test_openapi_artifact_evidence_rejects_stale_metadata(tmp_path: Path) -> None:
    artifact_path = tmp_path / "lotus-risk.openapi.json"
    schema = _valid_schema()
    write_openapi_artifact(schema, artifact_path)
    evidence = build_openapi_evidence(
        schema,
        artifact_path,
        generated_at_utc="2026-07-05T00:00:00Z",
        source_identity={
            "git_branch": "old-branch",
            "git_commit_sha": "old-commit",
            "repo_url": "https://github.com/sgajbi/lotus-risk",
            "ci_pipeline_run_id": "old-run",
        },
    )

    errors = validate_openapi_evidence(
        evidence,
        schema,
        artifact_path,
        source_identity={
            "git_branch": "refactor/enterprise-risk-backend",
            "git_commit_sha": "new-commit",
            "repo_url": "https://github.com/sgajbi/lotus-risk",
            "ci_pipeline_run_id": "new-run",
        },
    )

    assert "OpenAPI evidence field source is stale or invalid" in errors
