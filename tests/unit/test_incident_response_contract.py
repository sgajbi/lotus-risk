from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_incident_response_contract import (
    GOVERNED_RESPONSE_PROFILES_SHA256,
    _incident_contract_revision_sha256,
    _validate_exercise_evidence_references,
    _validate_incident_runbook,
    _validate_lifecycle_pointer_documents,
    validate_incident_response_contract,
)

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts" / "observability" / "lotus-risk-incident-response.v1.json"
MONITORING_PATH = REPO_ROOT / "contracts" / "observability" / "lotus-risk-monitoring.v1.json"
CONTRACT_REVISION_SHA256 = _incident_contract_revision_sha256(
    json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
)


def _contract() -> dict[str, Any]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_current_incident_response_contract_is_valid() -> None:
    assert validate_incident_response_contract() == []


def test_missing_alert_response_fails_closed(tmp_path: Path) -> None:
    payload = _contract()
    payload["alert_responses"].pop()

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("alert response coverage mismatch" in issue for issue in issues)


def test_unknown_evidence_field_fails_closed(tmp_path: Path) -> None:
    payload = _contract()
    payload["alert_responses"][0]["evidence_preservation"].append("raw_request_body")

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("unsafe or unknown fields" in issue for issue in issues)


@pytest.mark.parametrize("field", ["initial_containment", "recovery_reconciliation"])
def test_missing_response_actions_fail_closed(tmp_path: Path, field: str) -> None:
    payload = _contract()
    payload["alert_responses"][0][field] = []

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any(field in issue for issue in issues)


def test_unexercised_contract_cannot_claim_production_acceptance(tmp_path: Path) -> None:
    payload = _contract()
    payload["production_acceptance"] = True
    payload["exercise_evidence"]["production_claim"] = True

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("must not claim production acceptance" in issue for issue in issues)
    assert any("must not claim production readiness" in issue for issue in issues)


def test_exercised_status_requires_evidence_reference(tmp_path: Path) -> None:
    payload = _contract()
    payload["exercise_evidence"]["status"] = "exercised"

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("requires evidence references" in issue for issue in issues)
    assert any("contract status does not match exercise status" in issue for issue in issues)


def test_exercise_transition_requires_matching_runbook_posture(tmp_path: Path) -> None:
    payload = _contract()
    payload["status"] = "exercised"
    payload["exercise_evidence"]["status"] = "exercised"
    payload["exercise_evidence"]["evidence_references"] = ["exercise-run-123"]

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("documented contract posture does not match" in issue for issue in issues)


@pytest.mark.parametrize(
    "stale_assertion",
    [
        "The contract remains `prepared_not_exercised`.",
        "The contract remains prepared_not_exercised.",
        "The contract posture is prepared_not_exercised.",
    ],
)
def test_all_runbook_posture_assertions_must_match(tmp_path: Path, stale_assertion: str) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(
        current.replace(
            "Contract posture: `prepared_not_exercised`",
            "Contract posture: `exercised`",
        )
        + f"\n{stale_assertion}\n",
        encoding="utf-8",
    )

    issues = _validate_incident_runbook(
        "incident-response.md",
        contract_status="exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("stale or missing contract posture assertion" in issue for issue in issues)


def test_duplicate_production_acceptance_assertion_fails_closed(tmp_path: Path) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(current + "\n- Production acceptance: `true`\n", encoding="utf-8")

    issues = _validate_incident_runbook(
        "incident-response.md",
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("documented production acceptance does not match" in issue for issue in issues)


def test_plain_production_acceptance_contradiction_fails_closed(tmp_path: Path) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(current + "\nProduction acceptance is true.\n", encoding="utf-8")

    issues = _validate_incident_runbook(
        "incident-response.md",
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("documented production acceptance does not match" in issue for issue in issues)


def test_prefixed_production_acceptance_contradiction_fails_closed(tmp_path: Path) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(
        current + "\nFor this release, production acceptance is true.\n",
        encoding="utf-8",
    )

    issues = _validate_incident_runbook(
        "incident-response.md",
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("documented production acceptance does not match" in issue for issue in issues)


@pytest.mark.parametrize(
    "example",
    [
        "For example, production acceptance is true.",
        "Example configuration, production acceptance is true.",
    ],
)
def test_acceptance_examples_are_not_declarations(tmp_path: Path, example: str) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(current + f"\n{example}\n", encoding="utf-8")

    assert (
        _validate_incident_runbook(
            "incident-response.md",
            contract_status="prepared_not_exercised",
            production_acceptance=False,
            repository_root=tmp_path,
        )
        == []
    )


def test_reversed_documented_severity_mapping_fails_closed(tmp_path: Path) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(
        current.replace(
            "critical=SEV1,warning=SEV2",
            "critical=SEV2,warning=SEV1",
        ),
        encoding="utf-8",
    )

    issues = _validate_incident_runbook(
        "incident-response.md",
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("documented severity mapping does not match" in issue for issue in issues)


def test_duplicate_operational_severity_instruction_fails_closed(tmp_path: Path) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(
        current + "\nMap warnings to\n`SEV1`.\nMap critical monitoring alerts to\n`SEV2`.\n",
        encoding="utf-8",
    )

    issues = _validate_incident_runbook(
        "incident-response.md",
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("duplicates operational severity guidance" in issue for issue in issues)


@pytest.mark.parametrize(
    "instruction",
    [
        "SEV2 = critical and SEV1 = warning.",
        "Assign SEV2 to critical monitoring alerts.",
        "Critical alerts = SEV2.",
        "Critical alerts are SEV2.",
        "Critical alerts should be classified as SEV2.",
        "Critical alerts must map to SEV2.",
        "SEV2 should apply to critical alerts.",
        "Critical alerts should apply to SEV2.",
        "Set the severity of critical alerts to SEV2.",
        "Critical alerts have severity SEV2.",
        "Categorize critical alerts as SEV2.",
        "Classify all critical alerts as SEV2.",
        "Classify both critical alerts as SEV2.",
    ],
)
def test_alternate_severity_mapping_instruction_fails_closed(
    tmp_path: Path,
    instruction: str,
) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(current + f"\n{instruction}\n", encoding="utf-8")

    issues = _validate_incident_runbook(
        "incident-response.md",
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("duplicates operational severity guidance" in issue for issue in issues)


def test_permitted_severity_declaration_format_is_not_treated_as_duplicate(
    tmp_path: Path,
) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(
        current.replace(
            "- Monitoring severity mapping: `critical=SEV1,warning=SEV2`",
            "Monitoring severity mapping:    `critical=SEV1,warning=SEV2`",
        ),
        encoding="utf-8",
    )

    assert (
        _validate_incident_runbook(
            "incident-response.md",
            contract_status="prepared_not_exercised",
            production_acceptance=False,
            repository_root=tmp_path,
        )
        == []
    )


def test_non_mapping_severity_guidance_is_permitted(tmp_path: Path) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(
        current
        + "\nEscalate each SEV1 incident to the incident commander. "
        + "Search critical and warning logs during investigation.\n",
        encoding="utf-8",
    )

    assert (
        _validate_incident_runbook(
            "incident-response.md",
            contract_status="prepared_not_exercised",
            production_acceptance=False,
            repository_root=tmp_path,
        )
        == []
    )


def test_non_mapping_same_clause_severity_guidance_is_permitted(tmp_path: Path) -> None:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(
        current
        + "\nFor SEV1 incidents, responders are required to inspect critical alert telemetry.\n",
        encoding="utf-8",
    )

    assert (
        _validate_incident_runbook(
            "incident-response.md",
            contract_status="prepared_not_exercised",
            production_acceptance=False,
            repository_root=tmp_path,
        )
        == []
    )


def test_planned_status_requires_evidence_reference() -> None:
    assert _validate_exercise_evidence_references("planned", []) == [
        "planned status requires evidence references"
    ]


@pytest.mark.parametrize("status", ["planned", "exercised"])
def test_lifecycle_evidence_reference_must_resolve(
    tmp_path: Path,
    status: str,
) -> None:
    issues = _validate_exercise_evidence_references(
        status,
        ["evidence/incident-response-exercises/missing.json"],
        repository_root=tmp_path,
    )

    assert any("exercise evidence JSON does not exist" in issue for issue in issues)
    assert any("requires at least one valid passing" in issue for issue in issues) is (
        status == "exercised"
    )


def test_unrelated_repository_file_is_not_exercise_evidence(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Repository\n", encoding="utf-8")

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["README.md"],
        repository_root=tmp_path,
    )

    assert any("must use evidence/incident-response-exercises" in issue for issue in issues)


def test_exercise_result_requires_operational_evidence_fields(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/incomplete.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_result",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2026-10-03T05:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/incomplete.json"],
        repository_root=tmp_path,
    )

    assert any("scenario_alert_id must be a governed alert" in issue for issue in issues)
    assert any("owner_roles must be unique governed roles" in issue for issue in issues)
    assert any("executed_at must be a UTC timestamp" in issue for issue in issues)
    assert any("outcome must be passed or failed" in issue for issue in issues)
    assert any("evidence_digest must be lowercase SHA-256" in issue for issue in issues)


def test_exercise_result_rejects_impossible_timestamps(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/invalid-time.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_result",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2026-99-99T99:99:99Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": ["incident_commander"],
                "executed_at": "2026-99-99T99:99:99Z",
                "outcome": "failed",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_digest": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/invalid-time.json"],
        repository_root=tmp_path,
    )

    assert any("recorded_at must be a UTC timestamp" in issue for issue in issues)
    assert any("executed_at must be a UTC timestamp" in issue for issue in issues)


def test_exercise_result_rejects_unknown_fields_and_reversed_chronology(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/unsafe.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_result",
                "exercise_id": "client-PB001-credential-secret",
                "recorded_at": "2026-10-03T05:00:00Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": ["incident_commander"],
                "executed_at": "2026-10-03T06:00:00Z",
                "outcome": "failed",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_digest": "a" * 64,
                "raw_payload": "forbidden",
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/unsafe.json"],
        repository_root=tmp_path,
    )

    assert any("extra=['raw_payload']" in issue for issue in issues)
    assert any("exercise_id must be a bounded opaque identifier" in issue for issue in issues)
    assert any("executed_at must not follow recorded_at" in issue for issue in issues)


def test_exercise_evidence_filename_must_equal_opaque_id(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/client-PB001-credential-secret.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_result",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2026-10-03T05:00:00Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": ["incident_commander"],
                "executed_at": "2026-10-03T04:00:00Z",
                "outcome": "failed",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_digest": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/client-PB001-credential-secret.json"],
        repository_root=tmp_path,
    )

    assert any("filename must equal the opaque exercise_id" in issue for issue in issues)


def test_exercise_evidence_must_be_direct_governed_child(tmp_path: Path) -> None:
    evidence = (
        tmp_path
        / "evidence/incident-response-exercises/client-PB001-credential-secret"
        / "exercise-0123456789abcdef.json"
    )
    evidence.parent.mkdir(parents=True)
    evidence.write_text("{}", encoding="utf-8")

    issues = _validate_exercise_evidence_references(
        "exercised",
        [
            (
                "evidence/incident-response-exercises/"
                "client-PB001-credential-secret/exercise-0123456789abcdef.json"
            )
        ],
        repository_root=tmp_path,
    )

    assert any("exercise evidence must be a direct governed child" in issue for issue in issues)


def test_exercise_evidence_reference_must_be_canonical(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence/incident-response-exercises"
    (evidence_root / "client-PB001-credential-secret").mkdir(parents=True)
    (evidence_root / "exercise-0123456789abcdef.json").write_text("{}", encoding="utf-8")

    issues = _validate_exercise_evidence_references(
        "exercised",
        [
            (
                "evidence/incident-response-exercises/"
                "client-PB001-credential-secret/../exercise-0123456789abcdef.json"
            )
        ],
        repository_root=tmp_path,
    )

    assert any("must equal the canonical direct-child path" in issue for issue in issues)


def test_exercise_plan_rejects_reversed_chronology(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/late-plan.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_plan",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2026-10-03T05:00:00Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": ["incident_commander"],
                "scheduled_for": "2026-10-03T04:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "planned",
        ["evidence/incident-response-exercises/late-plan.json"],
        repository_root=tmp_path,
    )

    assert any("scheduled_for must not precede recorded_at" in issue for issue in issues)


def test_secondary_document_cannot_duplicate_lifecycle_posture(tmp_path: Path) -> None:
    pointer_paths = (
        Path("REPOSITORY-ENGINEERING-CONTEXT.md"),
        Path("docs/observability.md"),
        Path("wiki/Operations-Runbook.md"),
    )
    for relative_path in pointer_paths:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("See the incident runbook.\n", encoding="utf-8")
    (tmp_path / "docs/observability.md").write_text(
        "Repository proof remains `prepared_not_exercised`.\n",
        encoding="utf-8",
    )

    issues = _validate_lifecycle_pointer_documents(tmp_path)

    assert any("duplicates lifecycle posture" in issue for issue in issues)


@pytest.mark.parametrize(
    "text",
    [
        "This check is exercised by a focused test.\n",
        "The contract remains exercised by the focused CI test.\n",
    ],
)
def test_secondary_document_may_use_exercised_as_ordinary_prose(tmp_path: Path, text: str) -> None:
    for relative_path in (
        Path("REPOSITORY-ENGINEERING-CONTEXT.md"),
        Path("docs/observability.md"),
        Path("wiki/Operations-Runbook.md"),
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    assert _validate_lifecycle_pointer_documents(tmp_path) == []


def test_secondary_document_may_explain_rejected_acceptance_configuration(
    tmp_path: Path,
) -> None:
    for relative_path in (
        Path("REPOSITORY-ENGINEERING-CONTEXT.md"),
        Path("docs/observability.md"),
        Path("wiki/Operations-Runbook.md"),
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("The validator rejects `production_acceptance=true`.\n", encoding="utf-8")

    assert _validate_lifecycle_pointer_documents(tmp_path) == []


@pytest.mark.parametrize("version", [None, "2.0.0"])
def test_contract_version_is_fixed(tmp_path: Path, version: str | None) -> None:
    payload = _contract()
    if version is None:
        payload.pop("contract_version")
    else:
        payload["contract_version"] = version

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("contract_version must be 1.0.0" in issue for issue in issues)


def test_exercised_status_rejects_stale_exercise_blocker(tmp_path: Path) -> None:
    payload = _contract()
    payload["status"] = "exercised"
    payload["exercise_evidence"]["status"] = "exercised"
    payload["exercise_evidence"]["evidence_references"] = ["exercise-run-123"]

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("deployment blockers do not match" in issue for issue in issues)


def test_unresolved_deployment_blocker_cannot_be_deleted(tmp_path: Path) -> None:
    payload = _contract()
    payload["deployment_blockers"].remove("approved contact-directory assignments")

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("approved contact-directory assignments" in issue for issue in issues)


def test_complete_exercised_transition_is_accepted(tmp_path: Path) -> None:
    runbook_dir = tmp_path / "docs/runbooks"
    runbook_dir.mkdir(parents=True)
    incident_runbook = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(
        encoding="utf-8"
    )
    (runbook_dir / "incident-response.md").write_text(
        incident_runbook.replace(
            "Contract posture: `prepared_not_exercised`",
            "Contract posture: `exercised`",
        ),
        encoding="utf-8",
    )
    (runbook_dir / "service-operations.md").write_text(
        (REPO_ROOT / "docs/runbooks/service-operations.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for relative_path in (
        Path("REPOSITORY-ENGINEERING-CONTEXT.md"),
        Path("docs/observability.md"),
        Path("wiki/Operations-Runbook.md"),
    ):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (REPO_ROOT / relative_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    payload = _contract()
    payload["status"] = "exercised"
    payload["exercise_evidence"]["status"] = "exercised"
    payload["deployment_blockers"].remove("executed incident exercise or incident-review evidence")
    contract_path = _write(tmp_path / "incident.json", payload)
    assert (
        validate_incident_response_contract(
            contract_path,
            MONITORING_PATH,
            enforce_exercise_evidence=False,
            repository_root=tmp_path,
        )
        == []
    )
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
    evidence.parent.mkdir(parents=True)
    artifact = evidence.parent / "artifacts/evidence-0123456789abcdef.json"
    artifact.parent.mkdir()
    artifact_json = '{"alert_id":"lotus-risk-http-5xx","bounded_correlation_reference":"correlation-0123456789abcdef","deployment_event_reference":"deployment-event-0123456789abcdef","exercise_id":"exercise-0123456789abcdef","image_digest":"sha256:0000000000000000000000000000000000000000000000000000000000000000","reconciliation_result":"passed","release_sha":"0000000000000000000000000000000000000000","timestamp_utc":"2026-10-03T04:30:00Z"}'
    artifact.write_text(artifact_json, encoding="utf-8")
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_result",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2026-10-03T05:00:00Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": [
                    "incident_commander",
                    "service_support_owner",
                    "platform_operations_owner",
                ],
                "executed_at": "2026-10-03T04:30:00Z",
                "outcome": "passed",
                "contract_revision_sha256": _incident_contract_revision_sha256(
                    payload,
                    monitoring_path=MONITORING_PATH,
                    repository_root=tmp_path,
                ),
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_artifact_reference": artifact.relative_to(tmp_path).as_posix(),
                "evidence_digest": sha256(artifact.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    payload["exercise_evidence"]["evidence_references"] = [
        "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
    ]
    issues = validate_incident_response_contract(
        _write(contract_path, payload),
        MONITORING_PATH,
        repository_root=tmp_path,
    )
    assert issues == []


@pytest.mark.parametrize("reference", ["", "   "])
def test_exercised_status_rejects_blank_evidence_reference(tmp_path: Path, reference: str) -> None:
    payload = _contract()
    payload["status"] = "exercised"
    payload["exercise_evidence"]["status"] = "exercised"
    payload["exercise_evidence"]["evidence_references"] = [reference]

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("must be nonblank strings" in issue for issue in issues)


@pytest.mark.parametrize("incident_class", ["", "   "])
def test_incident_class_is_required(tmp_path: Path, incident_class: str) -> None:
    payload = _contract()
    payload["alert_responses"][0]["incident_class"] = incident_class

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("incident_class is required" in issue for issue in issues)


@pytest.mark.parametrize("alert_id", ["", "   "])
def test_matching_blank_alert_ids_fail_closed(tmp_path: Path, alert_id: str) -> None:
    payload = _contract()
    monitoring = json.loads(MONITORING_PATH.read_text(encoding="utf-8"))
    payload["alert_responses"][0]["alert_id"] = alert_id
    monitoring["alerts"][0]["alert_id"] = alert_id

    issues = validate_incident_response_contract(
        _write(tmp_path / "incident.json", payload),
        _write(tmp_path / "monitoring.json", monitoring),
    )

    assert any("nonblank string alert_id" in issue for issue in issues)


def test_paired_alert_deletion_fails_closed(tmp_path: Path) -> None:
    payload = _contract()
    monitoring = json.loads(MONITORING_PATH.read_text(encoding="utf-8"))
    removed_alert_id = "lotus-risk-scenario-job-retryable-error"
    payload["alert_responses"] = [
        response
        for response in payload["alert_responses"]
        if response["alert_id"] != removed_alert_id
    ]
    monitoring["alerts"] = [
        alert for alert in monitoring["alerts"] if alert["alert_id"] != removed_alert_id
    ]

    issues = validate_incident_response_contract(
        _write(tmp_path / "incident.json", payload),
        _write(tmp_path / "monitoring.json", monitoring),
    )

    assert any("governed monitoring alert inventory mismatch" in issue for issue in issues)


@pytest.mark.parametrize("meaning", ["", "   "])
def test_severity_meaning_must_be_nonblank(tmp_path: Path, meaning: str) -> None:
    payload = _contract()
    payload["severity_model"]["SEV1"]["meaning"] = meaning

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("SEV1: severity meaning is required" in issue for issue in issues)


def test_severity_meaning_must_match_governed_definition(tmp_path: Path) -> None:
    payload = _contract()
    payload["severity_model"]["SEV1"]["meaning"] = "Routine informational event."

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("severity meaning does not match" in issue for issue in issues)


def test_alert_runbook_must_match_monitoring_contract(tmp_path: Path) -> None:
    payload = deepcopy(_contract())
    payload["alert_responses"][0]["runbook"] = (
        "docs/runbooks/service-operations.md#missing-alert-anchor"
    )

    issues = validate_incident_response_contract(
        _write(tmp_path / "incident.json", payload), MONITORING_PATH
    )

    assert any("runbook does not match monitoring contract" in issue for issue in issues)
    assert any("runbook anchor does not exist" in issue for issue in issues)


def test_incident_runbook_reference_is_required(tmp_path: Path) -> None:
    payload = _contract()
    payload["incident_runbook"] = "docs/runbooks/missing-incident-response.md"

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("incident runbook does not exist" in issue for issue in issues)


def test_incident_runbook_reference_cannot_move_to_an_in_repository_copy(
    tmp_path: Path,
) -> None:
    payload = _contract()
    payload["incident_runbook"] = "docs/runbooks/service-operations.md"

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any(
        "incident_runbook must remain docs/runbooks/incident-response.md" in issue
        for issue in issues
    )


@pytest.mark.parametrize("reference", ["../outside.md", "C:/outside.md"])
def test_incident_runbook_must_remain_inside_repository(tmp_path: Path, reference: str) -> None:
    issues = _validate_incident_runbook(
        reference,
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )

    assert any("must remain inside the repository" in issue for issue in issues)


def test_critical_alert_cannot_be_downgraded(tmp_path: Path) -> None:
    payload = _contract()
    response = next(
        item for item in payload["alert_responses"] if item["alert_id"] == "lotus-risk-http-5xx"
    )
    response["incident_severity"] = "SEV2"

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("critical monitoring alerts must map to SEV1" in issue for issue in issues)


def test_critical_alert_cannot_be_downgraded_in_both_contracts(tmp_path: Path) -> None:
    payload = _contract()
    monitoring = json.loads(MONITORING_PATH.read_text(encoding="utf-8"))
    alert_id = "lotus-risk-http-5xx"
    response = next(item for item in payload["alert_responses"] if item["alert_id"] == alert_id)
    alert = next(item for item in monitoring["alerts"] if item["alert_id"] == alert_id)
    response["monitoring_severity"] = "warning"
    response["incident_severity"] = "SEV2"
    alert["severity"] = "warning"

    issues = validate_incident_response_contract(
        _write(tmp_path / "incident.json", payload),
        _write(tmp_path / "monitoring.json", monitoring),
    )

    assert any("governed alert severities do not match" in issue for issue in issues)


@pytest.mark.parametrize("field", ["initial_containment", "recovery_reconciliation"])
def test_placeholder_alert_action_fails_closed(tmp_path: Path, field: str) -> None:
    payload = _contract()
    payload["alert_responses"][0][field] = ["noop"]

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("governed per-alert response profiles do not match" in issue for issue in issues)


def test_paired_runbook_remap_fails_closed(tmp_path: Path) -> None:
    payload = _contract()
    monitoring = json.loads(MONITORING_PATH.read_text(encoding="utf-8"))
    alert_id = "lotus-risk-http-5xx"
    replacement = "docs/runbooks/service-operations.md#endpoint-failure-rate-alert"
    next(item for item in payload["alert_responses"] if item["alert_id"] == alert_id)["runbook"] = (
        replacement
    )
    next(item for item in monitoring["alerts"] if item["alert_id"] == alert_id)["runbook"] = (
        replacement
    )

    issues = validate_incident_response_contract(
        _write(tmp_path / "incident.json", payload),
        _write(tmp_path / "monitoring.json", monitoring),
    )

    assert any("governed per-alert response profiles do not match" in issue for issue in issues)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("incident_class", "noop"),
        ("evidence_preservation", ["alert_id"]),
        ("escalation_roles", ["incident_commander"]),
    ],
)
def test_alert_specific_response_profile_reduction_fails_closed(
    tmp_path: Path, field: str, value: str | list[str]
) -> None:
    payload = _contract()
    response = next(
        item
        for item in payload["alert_responses"]
        if item["alert_id"] == "lotus-risk-upstream-dependency-failures"
    )
    response[field] = value

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("governed per-alert response profiles do not match" in issue for issue in issues)


def test_sev1_alert_requires_incident_commander(tmp_path: Path) -> None:
    payload = _contract()
    response = next(
        item for item in payload["alert_responses"] if item["alert_id"] == "lotus-risk-http-5xx"
    )
    response["escalation_roles"] = ["service_support_owner"]

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("SEV1 escalation requires incident_commander" in issue for issue in issues)


def test_sev2_alert_requires_service_support_owner(tmp_path: Path) -> None:
    payload = _contract()
    response = next(
        item
        for item in payload["alert_responses"]
        if item["alert_id"] == "lotus-risk-endpoint-failure-rate"
    )
    response["escalation_roles"] = ["security_response_owner"]

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("SEV2 escalation requires service_support_owner" in issue for issue in issues)


@pytest.mark.parametrize("actions", [["noop"], ["rotate_credential"]])
def test_credential_response_requires_complete_governed_actions(
    tmp_path: Path, actions: list[str]
) -> None:
    payload = _contract()
    payload["credential_response"]["actions"] = actions

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("must match the governed action set" in issue for issue in issues)


@pytest.mark.parametrize("field", ["required_fields", "allowed_statuses"])
@pytest.mark.parametrize("shape", ["object", "duplicate"])
def test_corrective_action_vocabularies_require_unique_string_arrays(
    tmp_path: Path, field: str, shape: str
) -> None:
    payload = _contract()
    values = payload["corrective_action_model"][field]
    payload["corrective_action_model"][field] = (
        {value: True for value in values} if shape == "object" else [*values, values[0]]
    )

    issues = validate_incident_response_contract(_write(tmp_path / "incident.json", payload))

    assert any("corrective action" in issue for issue in issues)


def test_shipped_cli_exits_nonzero_for_incomplete_alert_coverage(tmp_path: Path) -> None:
    payload = _contract()
    payload["alert_responses"].pop()
    bad_contract = _write(tmp_path / "incident.json", payload)

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "validate_incident_response_contract.py"),
            "--contract",
            str(bad_contract),
            "--monitoring-contract",
            str(MONITORING_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "alert response coverage mismatch" in result.stdout
