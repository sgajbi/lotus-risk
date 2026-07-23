from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from app.evidence.idea_opportunity_runtime import (
    CONSUMER_BLOCKERS_SATISFIED,
    REMAINING_CERTIFICATION_BLOCKERS,
    SCHEMA_VERSION,
    build_idea_opportunity_runtime_evidence,
    idea_opportunity_runtime_evidence_is_valid,
)
from app.main import app
from scripts import generate_idea_opportunity_runtime_evidence


GENERATED_AT = datetime(2026, 7, 23, 6, 30, tzinfo=UTC)


def _execute(route: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
    response = TestClient(app).post(route, json=payload)
    return response.status_code, response.json()


def _payload() -> dict[str, Any]:
    return build_idea_opportunity_runtime_evidence(
        execute=_execute,
        generated_at_utc=GENERATED_AT,
    )


def test_idea_opportunity_runtime_evidence_executes_three_source_products() -> None:
    payload = _payload()

    assert payload["schemaVersion"] == SCHEMA_VERSION
    assert payload["evidenceClass"] == "runtime_execution"
    assert payload["runtimeBoundary"] == "lotus-risk:http-api"
    assert payload["consumerBlockersSatisfied"] == list(CONSUMER_BLOCKERS_SATISFIED)
    assert payload["remainingCertificationBlockers"] == list(REMAINING_CERTIFICATION_BLOCKERS)
    assert [item["receipt"]["productId"] for item in payload["executions"]] == [
        "lotus-risk:ConcentrationRiskReport:v1",
        "lotus-risk:RiskMetricsReport:v1",
        "lotus-risk:DrawdownAnalyticsReport:v1",
    ]
    assert all(item["receipt"]["statusCode"] == 200 for item in payload["executions"])
    assert all(item["receipt"]["supportabilityState"] == "ready" for item in payload["executions"])
    assert idea_opportunity_runtime_evidence_is_valid(payload) is True


def test_idea_opportunity_runtime_evidence_is_source_safe() -> None:
    serialized = json.dumps(_payload(), sort_keys=True)

    assert "PB_SG_GLOBAL_BAL_001" not in serialized
    assert "SOURCE_SAFE_POSITION" not in serialized
    assert "SOURCE_SAFE_ISSUER" not in serialized
    assert "portfolioIdentityDigest" in serialized


def test_idea_opportunity_runtime_evidence_keeps_non_proof_boundaries() -> None:
    payload = _payload()

    claims = payload["nonProofClaims"]
    assert claims["officialRiskCalculationOwned"] == "lotus-risk"
    assert claims["ideaCandidatePersistenceObserved"] is False
    assert claims["gatewayWorkbenchRuntimeObserved"] is False
    assert claims["supportedFeaturePromoted"] is False


def test_idea_opportunity_runtime_evidence_rejects_inflated_unknown_or_static_claims() -> None:
    payload = _payload()
    inflated = deepcopy(payload)
    inflated["productionCertified"] = True
    assert idea_opportunity_runtime_evidence_is_valid(inflated) is False

    static_claim = deepcopy(payload)
    static_claim["evidenceClass"] = "source_design_contract"
    static_claim["evidenceDigest"] = _recompute_digest(static_claim)
    assert idea_opportunity_runtime_evidence_is_valid(static_claim) is False

    supported_feature_claim = deepcopy(payload)
    supported_feature_claim["nonProofClaims"]["supportedFeaturePromoted"] = True
    supported_feature_claim["evidenceDigest"] = _recompute_digest(supported_feature_claim)
    assert idea_opportunity_runtime_evidence_is_valid(supported_feature_claim) is False


def test_idea_opportunity_runtime_evidence_rejects_product_route_and_digest_drift() -> None:
    payload = _payload()

    wrong_product = deepcopy(payload)
    wrong_product["executions"][0]["receipt"]["productId"] = "lotus-risk:Other:v1"
    wrong_product["executions"][0]["receiptDigest"] = _receipt_digest(wrong_product, 0)
    wrong_product["evidenceDigest"] = _recompute_digest(wrong_product)
    assert idea_opportunity_runtime_evidence_is_valid(wrong_product) is False

    forged_summary = deepcopy(payload)
    forged_summary["executions"][1]["receipt"]["summary"]["volatilityPercent"] = 0.0
    forged_summary["executions"][1]["receiptDigest"] = _receipt_digest(forged_summary, 1)
    forged_summary["evidenceDigest"] = _recompute_digest(forged_summary)
    assert idea_opportunity_runtime_evidence_is_valid(forged_summary) is False


def test_idea_opportunity_runtime_evidence_rejects_failed_runtime_execution() -> None:
    def failing_execute(route: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        return 503, {"metadata": {"calculation_supportability": {"state": "unavailable"}}}

    payload = build_idea_opportunity_runtime_evidence(
        execute=failing_execute,
        generated_at_utc=GENERATED_AT,
    )

    assert payload["executions"][0]["receipt"]["statusCode"] == 503
    assert idea_opportunity_runtime_evidence_is_valid(payload) is False


def test_idea_opportunity_runtime_evidence_cli_writes_valid_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response:
        def __init__(self, code: int, payload: Mapping[str, Any]) -> None:
            self.status_code = code
            self._payload = payload

        def json(self) -> Mapping[str, Any]:
            return self._payload

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, route: str, json: Mapping[str, Any]) -> _Response:
            status_code, body = _execute(route, json)
            return _Response(status_code, body)

    output = tmp_path / "idea-risk-runtime-evidence.json"
    monkeypatch.setattr("scripts.generate_idea_opportunity_runtime_evidence.httpx.Client", _Client)

    result = generate_idea_opportunity_runtime_evidence.main(
        [
            "--risk-base-url",
            "http://risk.test",
            "--generated-at-utc",
            "2026-07-23T06:30:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert idea_opportunity_runtime_evidence_is_valid(payload) is True


def _receipt_digest(payload: dict[str, Any], index: int) -> str:
    from app.evidence.idea_opportunity_runtime import sha256_json

    return sha256_json(payload["executions"][index]["receipt"])


def _recompute_digest(payload: dict[str, Any]) -> str:
    from app.evidence.idea_opportunity_runtime import sha256_json

    return sha256_json({key: value for key, value in payload.items() if key != "evidenceDigest"})
