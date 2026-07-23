from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from app.evidence.idea_opportunity_constants import (
    CANONICAL_AS_OF_DATE,
    CANONICAL_CONTRACT_PROVENANCE,
    CONSUMER_BLOCKERS_SATISFIED,
    REMAINING_CERTIFICATION_BLOCKERS,
    SCHEMA_VERSION,
)
from app.evidence.idea_opportunity_runtime import (
    build_idea_opportunity_runtime_evidence,
    idea_opportunity_runtime_evidence_is_valid,
    identity_hash,
)
from app.main import app
from scripts import generate_idea_opportunity_runtime_evidence
from tests.support.app_runtime import override_app_runtime
from tests.support.lotus_core_fakes import SimulationLotusCoreClient
from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


GENERATED_AT = datetime(2026, 7, 23, 6, 30, tzinfo=UTC)
_CANONICAL_RETURN_ROWS = (
    ("2026-04-06", "0.015"),
    ("2026-04-07", "-0.028"),
    ("2026-04-08", "0.011"),
    ("2026-04-09", "-0.016"),
    ("2026-04-10", "0.004"),
)
_CANONICAL_BENCHMARK_ROWS = (
    ("2026-04-06", "0.004"),
    ("2026-04-07", "-0.005"),
    ("2026-04-08", "0.003"),
    ("2026-04-09", "-0.004"),
    ("2026-04-10", "0.001"),
)


class _CanonicalCoreClient(SimulationLotusCoreClient):
    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        snapshot = await super().get_core_snapshot(
            portfolio_id=portfolio_id,
            request_payload=request_payload,
            correlation_id=correlation_id,
        )
        sections = snapshot.setdefault("sections", {})
        assert isinstance(sections, dict)
        sections["instrument_enrichment"] = [
            {
                "security_id": "SEC_A",
                "issuer_id": "SOURCE_SAFE_ISSUER_A",
                "ultimate_parent_issuer_id": "SOURCE_SAFE_PARENT_ISSUER_A",
            },
            {
                "security_id": "SEC_B",
                "issuer_id": "SOURCE_SAFE_ISSUER_A",
                "ultimate_parent_issuer_id": "SOURCE_SAFE_PARENT_ISSUER_A",
            },
        ]
        return snapshot


def _execute(route: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
    performance_client = RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=_CANONICAL_RETURN_ROWS,
            benchmark_returns=_CANONICAL_BENCHMARK_ROWS,
        )
    )
    core_client = _CanonicalCoreClient(
        session_id="SIM_IDEA_EVIDENCE",
        simulation_version=1,
        include_ultimate_parent_issuer_id=True,
    )
    with override_app_runtime(
        lotus_performance_client=performance_client,
        lotus_core_client=core_client,
    ):
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
    assert all(item["receipt"]["freshnessBucket"] == "current" for item in payload["executions"])
    assert idea_opportunity_runtime_evidence_is_valid(payload) is True


def test_idea_opportunity_runtime_evidence_uses_stateful_canonical_requests() -> None:
    seen: list[tuple[str, Mapping[str, Any]]] = []

    def recording_execute(route: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        seen.append((route, payload))
        return _execute(route, payload)

    payload = build_idea_opportunity_runtime_evidence(
        execute=recording_execute,
        generated_at_utc=GENERATED_AT,
    )

    assert idea_opportunity_runtime_evidence_is_valid(payload) is True
    assert [request["input_mode"] for _, request in seen] == ["stateful", "stateful", "stateful"]
    for _, request in seen:
        stateful_input = request["stateful_input"]
        assert isinstance(stateful_input, Mapping)
        assert stateful_input["portfolio_id"] == "PB_SG_GLOBAL_BAL_001"
        assert stateful_input["as_of_date"] == CANONICAL_AS_OF_DATE.isoformat()

    drawdown_request = dict(seen[2][1])
    drawdown_stateful_input = drawdown_request["stateful_input"]
    assert "benchmark_policy" not in drawdown_request
    assert drawdown_stateful_input["benchmark_policy"] == {
        "include_benchmark": True,
        "missing_benchmark_policy": "REQUIRE",
    }


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


def test_idea_opportunity_runtime_evidence_binds_canonical_contract_provenance() -> None:
    payload = _payload()

    assert payload["contractProvenance"] == CANONICAL_CONTRACT_PROVENANCE

    forged = deepcopy(payload)
    forged["contractProvenance"]["canonicalDemoDataContract"]["contentDigest"] = "sha256:forged"
    forged["evidenceDigest"] = _recompute_digest(forged)

    assert idea_opportunity_runtime_evidence_is_valid(forged) is False
    assert CANONICAL_CONTRACT_PROVENANCE["canonicalDemoDataContract"]["contentDigest"] != (
        "sha256:forged"
    )


def test_idea_opportunity_runtime_evidence_rejects_noncanonical_portfolio_proof() -> None:
    with pytest.raises(ValueError, match="PB_SG_GLOBAL_BAL_001"):
        build_idea_opportunity_runtime_evidence(
            execute=_execute,
            generated_at_utc=GENERATED_AT,
            portfolio_id="PB_SG_OTHER_001",
        )

    payload = _payload()
    forged = deepcopy(payload)
    forged["portfolioBinding"]["portfolioIdentityDigest"] = identity_hash("PB_SG_OTHER_001")
    forged["evidenceDigest"] = _recompute_digest(forged)

    assert idea_opportunity_runtime_evidence_is_valid(forged) is False


def test_idea_opportunity_runtime_evidence_rejects_noncanonical_as_of_date() -> None:
    with pytest.raises(ValueError, match=CANONICAL_AS_OF_DATE.isoformat()):
        build_idea_opportunity_runtime_evidence(
            execute=_execute,
            generated_at_utc=GENERATED_AT,
            as_of_date=date(2026, 4, 11),
        )

    payload = _payload()
    forged = deepcopy(payload)
    forged["executions"][0]["receipt"]["asOfDate"] = "2026-04-11"
    forged["executions"][0]["receiptDigest"] = _receipt_digest(forged, 0)
    forged["evidenceDigest"] = _recompute_digest(forged)

    assert idea_opportunity_runtime_evidence_is_valid(forged) is False


def test_idea_opportunity_runtime_evidence_rejects_receipt_portfolio_digest_drift() -> None:
    payload = _payload()
    forged = deepcopy(payload)
    forged["executions"][0]["receipt"]["portfolioIdentityDigest"] = identity_hash("PB_SG_OTHER_001")
    forged["executions"][0]["receiptDigest"] = _receipt_digest(forged, 0)
    forged["evidenceDigest"] = _recompute_digest(forged)

    assert idea_opportunity_runtime_evidence_is_valid(forged) is False


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

    missing_non_proof_claim = deepcopy(payload)
    del missing_non_proof_claim["nonProofClaims"]["gatewayWorkbenchRuntimeObserved"]
    missing_non_proof_claim["evidenceDigest"] = _recompute_digest(missing_non_proof_claim)
    assert idea_opportunity_runtime_evidence_is_valid(missing_non_proof_claim) is False


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


def test_idea_opportunity_runtime_evidence_rejects_request_payload_digest_drift() -> None:
    payload = _payload()
    forged = deepcopy(payload)
    forged["executions"][1]["receipt"]["requestPayloadDigest"] = identity_hash("forged-request")
    forged["executions"][1]["receiptDigest"] = _receipt_digest(forged, 1)
    forged["evidenceDigest"] = _recompute_digest(forged)

    assert idea_opportunity_runtime_evidence_is_valid(forged) is False


def test_idea_opportunity_runtime_evidence_rejects_empty_runtime_summaries() -> None:
    payload = _payload()

    for index in range(3):
        forged = deepcopy(payload)
        forged["executions"][index]["receipt"]["summary"] = {}
        forged["executions"][index]["receipt"]["normalizedResponseDigest"] = _summary_digest(
            forged, index
        )
        forged["executions"][index]["receiptDigest"] = _receipt_digest(forged, index)
        forged["evidenceDigest"] = _recompute_digest(forged)

        assert idea_opportunity_runtime_evidence_is_valid(forged) is False


def test_idea_opportunity_runtime_evidence_rejects_forged_bounded_summary_values() -> None:
    payload = _payload()

    forged_concentration = deepcopy(payload)
    forged_concentration["executions"][0]["receipt"]["summary"]["coverageStatus"] = "forged"
    _recompute_execution_and_evidence_digests(forged_concentration, 0)
    assert idea_opportunity_runtime_evidence_is_valid(forged_concentration) is False

    forged_risk = deepcopy(payload)
    forged_risk["executions"][1]["receipt"]["summary"]["volatilityPercent"] = 10_000
    _recompute_execution_and_evidence_digests(forged_risk, 1)
    assert idea_opportunity_runtime_evidence_is_valid(forged_risk) is False

    forged_drawdown = deepcopy(payload)
    forged_drawdown["executions"][2]["receipt"]["summary"]["episodeCount"] = 0
    _recompute_execution_and_evidence_digests(forged_drawdown, 2)
    assert idea_opportunity_runtime_evidence_is_valid(forged_drawdown) is False


def test_idea_opportunity_runtime_evidence_rejects_non_finite_summary_values() -> None:
    payload = _payload()
    forged = deepcopy(payload)
    forged["executions"][1]["receipt"]["summary"]["volatilityPercent"] = float("nan")
    _recompute_execution_and_evidence_digests(forged, 1)

    assert idea_opportunity_runtime_evidence_is_valid(forged) is False


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
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: object) -> None:
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


def test_idea_opportunity_runtime_evidence_cli_rejects_noncanonical_portfolio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    output = tmp_path / "idea-risk-runtime-evidence.json"
    monkeypatch.setattr("scripts.generate_idea_opportunity_runtime_evidence.httpx.Client", _Client)

    with pytest.raises(ValueError, match="PB_SG_GLOBAL_BAL_001"):
        generate_idea_opportunity_runtime_evidence.main(
            [
                "--risk-base-url",
                "http://risk.test",
                "--portfolio-id",
                "PB_SG_OTHER_001",
                "--generated-at-utc",
                "2026-07-23T06:30:00Z",
                "--output",
                str(output),
            ]
        )


def test_idea_opportunity_runtime_evidence_cli_rejects_noncanonical_as_of_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    output = tmp_path / "idea-risk-runtime-evidence.json"
    monkeypatch.setattr("scripts.generate_idea_opportunity_runtime_evidence.httpx.Client", _Client)

    with pytest.raises(ValueError, match=CANONICAL_AS_OF_DATE.isoformat()):
        generate_idea_opportunity_runtime_evidence.main(
            [
                "--risk-base-url",
                "http://risk.test",
                "--as-of-date",
                "2026-04-11",
                "--generated-at-utc",
                "2026-07-23T06:30:00Z",
                "--output",
                str(output),
            ]
        )


def test_idea_opportunity_runtime_evidence_script_bootstraps_repo_src_before_app_import() -> None:
    source = Path(generate_idea_opportunity_runtime_evidence.__file__).read_text(encoding="utf-8")

    assert source.index("force_repo_src_first(PROJECT_ROOT)") < source.index(
        "from app.evidence.idea_opportunity_runtime import"
    )


def _receipt_digest(payload: dict[str, Any], index: int) -> str:
    from app.evidence.idea_opportunity_runtime import sha256_json

    return sha256_json(payload["executions"][index]["receipt"])


def _summary_digest(payload: dict[str, Any], index: int) -> str:
    from app.evidence.idea_opportunity_runtime import sha256_json

    return sha256_json(payload["executions"][index]["receipt"]["summary"])


def _recompute_digest(payload: dict[str, Any]) -> str:
    from app.evidence.idea_opportunity_runtime import sha256_json

    return sha256_json({key: value for key, value in payload.items() if key != "evidenceDigest"})


def _recompute_execution_and_evidence_digests(payload: dict[str, Any], index: int) -> None:
    payload["executions"][index]["receipt"]["normalizedResponseDigest"] = _summary_digest(
        payload, index
    )
    payload["executions"][index]["receiptDigest"] = _receipt_digest(payload, index)
    payload["evidenceDigest"] = _recompute_digest(payload)
