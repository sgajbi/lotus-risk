import hashlib
import json
import sys
from pathlib import Path

import pytest

from scripts.validate_incident_response_contract import (
    GOVERNED_RESPONSE_PROFILES_SHA256,
    _incident_contract_revision_sha256,
    _validate_evidence_artifact,
    _validate_exercise_evidence_references,
    _validate_incident_runbook,
    main,
    validate_incident_response_contract,
)

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts/observability/lotus-risk-incident-response.v1.json"
CONTRACT_REVISION_SHA256 = _incident_contract_revision_sha256(
    json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
)


def _issues_for_guidance(tmp_path: Path, guidance: str) -> list[str]:
    runbook = tmp_path / "incident-response.md"
    current = (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8")
    runbook.write_text(current + f"\n{guidance}\n", encoding="utf-8")
    return _validate_incident_runbook(
        "incident-response.md",
        contract_status="prepared_not_exercised",
        production_acceptance=False,
        repository_root=tmp_path,
    )


def _write_evidence_artifact(tmp_path: Path) -> tuple[str, str]:
    reference = "evidence/incident-response-exercises/artifacts/evidence-0123456789abcdef.json"
    path = tmp_path / reference
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "alert_id": "lotus-risk-http-5xx",
                "bounded_correlation_reference": "correlation-0123456789abcdef",
                "deployment_event_reference": "deployment-event-0123456789abcdef",
                "exercise_id": "exercise-0123456789abcdef",
                "image_digest": f"sha256:{'0' * 64}",
                "reconciliation_result": "passed",
                "release_sha": "0" * 40,
                "timestamp_utc": "2026-10-03T04:30:00Z",
            }
        ),
        encoding="utf-8",
    )
    return reference, hashlib.sha256(path.read_bytes()).hexdigest()


def test_configuration_word_does_not_hide_acceptance_claim(tmp_path: Path) -> None:
    issues = _issues_for_guidance(
        tmp_path,
        "Regardless of configuration, production acceptance is true.",
    )

    assert any("documented production acceptance does not match" in issue for issue in issues)


def test_wrapped_production_acceptance_claim_fails_closed(tmp_path: Path) -> None:
    issues = _issues_for_guidance(tmp_path, "Production\nacceptance is true.")

    assert any("documented production acceptance does not match" in issue for issue in issues)


@pytest.mark.parametrize(
    "claim",
    ["Production acceptance remains true.", "Production\nacceptance remains true."],
)
def test_remains_production_acceptance_claim_fails_closed(tmp_path: Path, claim: str) -> None:
    issues = _issues_for_guidance(tmp_path, claim)

    assert any("documented production acceptance does not match" in issue for issue in issues)


@pytest.mark.parametrize(
    "claim",
    ["Production acceptance has been granted.", "Production acceptance is approved."],
)
def test_noncanonical_production_acceptance_claims_fail_closed(tmp_path: Path, claim: str) -> None:
    issues = _issues_for_guidance(tmp_path, claim)

    assert any("documented production acceptance does not match" in issue for issue in issues)


@pytest.mark.parametrize(
    "claim",
    [
        "The contract is exercised.",
        "For this release, the contract is exercised.",
        "It is true that the contract is exercised.",
        "Contract status: exercised.",
        "Contract status remains exercised.",
        "Contract\nstatus: exercised.",
        "The contract has been exercised.",
        "The contract is now exercised.",
        "The contract has already been exercised.",
        "The contract has currently been exercised.",
    ],
)
def test_direct_stale_contract_status_assertion_fails_closed(tmp_path: Path, claim: str) -> None:
    issues = _issues_for_guidance(tmp_path, claim)

    assert any("stale or missing contract posture assertion" in issue for issue in issues)


@pytest.mark.parametrize(
    "guidance",
    [
        "The contract is not exercised.",
        "Do not mark the contract exercised until a valid passing result exists.",
        "It is false that the contract is exercised.",
    ],
)
def test_negated_contract_status_guidance_is_permitted(tmp_path: Path, guidance: str) -> None:
    assert _issues_for_guidance(tmp_path, guidance) == []


@pytest.mark.parametrize(
    "guidance",
    [
        "The contract is not prepared_not_exercised.",
        "It is false that the contract is prepared_not_exercised.",
        "Contract posture is not prepared_not_exercised.",
        "Contract status is not prepared_not_exercised.",
        "It is false that the contract has been prepared_not_exercised.",
        "It is false that repository proof has already been prepared_not_exercised.",
        "The contract has never been prepared_not_exercised.",
        "Contract posture has never been prepared_not_exercised.",
        "Contract status has never been prepared_not_exercised.",
        "The contract isn't prepared_not_exercised.",
        "The contract isn’t prepared_not_exercised.",
        "Contract status wasn't prepared_not_exercised.",
        "The contract hasn't been prepared_not_exercised.",
    ],
)
def test_denial_of_governed_contract_status_fails_closed(tmp_path: Path, guidance: str) -> None:
    issues = _issues_for_guidance(tmp_path, guidance)

    assert any("stale or missing contract posture assertion" in issue for issue in issues)


@pytest.mark.parametrize(
    "guidance",
    [
        "Never classify critical alerts as SEV2.",
        "Do not classify all critical alerts as SEV2.",
        "No critical alerts are SEV2.",
        "Not all warning alerts are SEV1.",
        "It is false that critical alerts are SEV2.",
        "Critical alerts aren't SEV2.",
    ],
)
def test_negated_mapping_guidance_is_permitted(tmp_path: Path, guidance: str) -> None:
    assert _issues_for_guidance(tmp_path, guidance) == []


@pytest.mark.parametrize(
    "guidance",
    [
        "Critical alerts are not SEV1.",
        "It is false that critical alerts are SEV1.",
        "No warning alerts are SEV2.",
        "Never classify critical alerts as SEV1.",
        "Critical alerts are no longer SEV1.",
        "Warnings are no longer SEV2.",
        "Critical alerts are never SEV1.",
        "Warnings are never SEV2.",
        "SEV1 no longer maps to critical alerts.",
        "SEV2 does not apply to warnings.",
        "SEV1 never maps to critical alerts.",
        "SEV2 never applies to warnings.",
        "Critical alerts aren't SEV1.",
        "Critical alerts aren’t SEV1.",
        "Warnings weren't SEV2.",
        "SEV1 doesn't map to critical alerts.",
        "SEV2 doesn't apply to warnings.",
        "Critical alerts don't map to SEV1.",
        "Critical alert doesn’t map to SEV1.",
        "Warnings don't map to SEV2.",
        "Warning doesn’t map to SEV2.",
    ],
)
def test_denial_of_governed_mapping_fails_closed(tmp_path: Path, guidance: str) -> None:
    issues = _issues_for_guidance(tmp_path, guidance)

    assert any("duplicates operational severity guidance" in issue for issue in issues)


def test_not_only_mapping_remains_an_affirmative_conflict(tmp_path: Path) -> None:
    issues = _issues_for_guidance(
        tmp_path,
        "Not only are critical alerts SEV2, they also require paging.",
    )

    assert any("duplicates operational severity guidance" in issue for issue in issues)


@pytest.mark.parametrize(
    "guidance",
    [
        "Critical alerts are now SEV2.",
        "Warnings are currently SEV1.",
        "Critical alerts remain SEV2.",
    ],
)
def test_adverb_qualified_mapping_is_an_affirmative_conflict(tmp_path: Path, guidance: str) -> None:
    issues = _issues_for_guidance(tmp_path, guidance)

    assert any("duplicates operational severity guidance" in issue for issue in issues)


@pytest.mark.parametrize("status", ["planned", "exercised"])
def test_lifecycle_evidence_accepts_repository_artifact(tmp_path: Path, status: str) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
    evidence.parent.mkdir(parents=True)
    artifact_reference, artifact_digest = _write_evidence_artifact(tmp_path)
    revision_fields = {
        "contract_revision_sha256": CONTRACT_REVISION_SHA256,
        "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
    }
    result_fields = {
        "executed_at": "2026-10-03T04:30:00Z",
        "outcome": "passed",
        "evidence_artifact_reference": artifact_reference,
        "evidence_digest": artifact_digest,
        **revision_fields,
    }
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_plan" if status == "planned" else "exercise_result",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2026-10-03T05:00:00Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": ["incident_commander"],
                **(
                    {"scheduled_for": "2099-10-10T05:00:00Z", **revision_fields}
                    if status == "planned"
                    else result_fields
                ),
            }
        ),
        encoding="utf-8",
    )

    assert (
        _validate_exercise_evidence_references(
            status,
            ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
            repository_root=tmp_path,
        )
        == []
    )


def test_http_5xx_pass_requires_reconciliation_evidence(tmp_path: Path) -> None:
    reference, _ = _write_evidence_artifact(tmp_path)
    artifact = tmp_path / reference
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload.pop("reconciliation_result")
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    issues = _validate_evidence_artifact(
        reference,
        hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "lotus-risk-http-5xx",
        "passed",
        "exercise-0123456789abcdef",
        "2026-10-03T04:30:00Z",
        {
            "alert_id",
            "bounded_correlation_reference",
            "deployment_event_reference",
            "exercise_id",
            "image_digest",
            "reconciliation_result",
            "release_sha",
            "timestamp_utc",
        },
        repository_root=tmp_path,
    )

    assert any("fields do not match response profile" in issue for issue in issues)


@pytest.mark.parametrize(
    ("exercise_id", "executed_at", "message"),
    [
        ("exercise-fedcba9876543210", "2026-10-03T04:30:00Z", "exercise_id"),
        ("exercise-0123456789abcdef", "2026-10-03T04:31:00Z", "timestamp"),
    ],
)
def test_artifact_identity_must_match_exercise_result(
    tmp_path: Path, exercise_id: str, executed_at: str, message: str
) -> None:
    reference, digest = _write_evidence_artifact(tmp_path)

    issues = _validate_evidence_artifact(
        reference,
        digest,
        "lotus-risk-http-5xx",
        "passed",
        exercise_id,
        executed_at,
        None,
        repository_root=tmp_path,
    )

    assert any(f"{message} does not match result" in issue for issue in issues)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("escalation_model", "assigned_contacts", ["Jane Doe", "+65 6000 0000"]),
        ("credential_response", "inline_secret", "forbidden"),
    ],
)
def test_security_sensitive_sections_reject_undeclared_fields(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract[section][field] = value
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    issues = validate_incident_response_contract(path)

    assert any(f"{section} fields do not match the governed schema" in issue for issue in issues)


def test_exercise_result_rejects_future_timestamps(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_result",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2099-10-03T05:00:00Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": ["incident_commander"],
                "executed_at": "2099-10-03T04:30:00Z",
                "outcome": "passed",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_digest": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        repository_root=tmp_path,
    )

    assert any("recorded_at exceeds the bounded current-time skew" in issue for issue in issues)
    assert any("executed_at exceeds the bounded current-time skew" in issue for issue in issues)


def test_exercise_evidence_rejects_duplicate_object_keys(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
    evidence.parent.mkdir(parents=True)
    payload = {
        "artifact_version": "1.0.0",
        "contract_id": "lotus-risk:incident-response:v1",
        "evidence_type": "exercise_result",
        "exercise_id": "exercise-0123456789abcdef",
        "recorded_at": "2026-10-03T05:00:00Z",
        "scenario_alert_id": "lotus-risk-http-5xx",
        "owner_roles": ["incident_commander"],
        "executed_at": "2026-10-03T04:30:00Z",
        "outcome": "passed",
        "contract_revision_sha256": CONTRACT_REVISION_SHA256,
        "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
        "evidence_digest": "a" * 64,
    }
    serialized = json.dumps(payload).replace(
        '"exercise_id": "exercise-0123456789abcdef"',
        '"exercise_id": "client-PB001-credential-secret", '
        '"exercise_id": "exercise-0123456789abcdef"',
    )
    evidence.write_text(serialized, encoding="utf-8")

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        repository_root=tmp_path,
    )

    assert any("duplicate JSON object keys are forbidden" in issue for issue in issues)


def test_exercise_result_rejects_stale_contract_revisions(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
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
                "executed_at": "2026-10-03T04:30:00Z",
                "outcome": "passed",
                "contract_revision_sha256": "0" * 64,
                "response_profiles_sha256": "1" * 64,
                "evidence_digest": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        expected_contract_revision_sha256=CONTRACT_REVISION_SHA256,
        repository_root=tmp_path,
    )

    assert any("contract revision does not match" in issue for issue in issues)
    assert any("response profile revision does not match" in issue for issue in issues)


def test_contract_revision_includes_governed_runbook_content(tmp_path: Path) -> None:
    runbook = tmp_path / "docs/runbooks/incident-response.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text(
        (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    original = _incident_contract_revision_sha256(contract, repository_root=tmp_path)
    runbook.write_text(runbook.read_text(encoding="utf-8") + "\nChanged containment.\n")

    assert _incident_contract_revision_sha256(contract, repository_root=tmp_path) != original


def test_contract_revision_excludes_lifecycle_only_runbook_transition(tmp_path: Path) -> None:
    runbook = tmp_path / "docs/runbooks/incident-response.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text(
        (REPO_ROOT / "docs/runbooks/incident-response.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    original = _incident_contract_revision_sha256(contract, repository_root=tmp_path)
    contract["status"] = "exercised"
    contract["production_acceptance"] = True
    transitioned = runbook.read_text(encoding="utf-8").replace(
        "- Contract posture: `prepared_not_exercised`",
        "- Contract posture: `exercised`",
    )
    runbook.write_text(
        transitioned.replace(
            "- Production acceptance: `false`",
            "- Production acceptance: `true`",
        ),
        encoding="utf-8",
    )

    assert _incident_contract_revision_sha256(contract, repository_root=tmp_path) == original


def test_contract_revision_includes_monitoring_trigger_definitions(tmp_path: Path) -> None:
    monitoring_path = tmp_path / "lotus-risk-monitoring.v1.json"
    monitoring = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    monitoring_path.write_text(json.dumps(monitoring), encoding="utf-8")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    original = _incident_contract_revision_sha256(contract, monitoring_path=monitoring_path)
    http_5xx = next(
        alert for alert in monitoring["alerts"] if alert["alert_id"] == "lotus-risk-http-5xx"
    )
    http_5xx["query"] = "vector(0)"
    monitoring_path.write_text(json.dumps(monitoring), encoding="utf-8")

    assert _incident_contract_revision_sha256(contract, monitoring_path=monitoring_path) != original


def test_cli_reports_revision_for_selected_monitoring_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    monitoring = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    monitoring["purpose"] = "Selected valid monitoring contract for revision proof."
    monitoring_path.write_text(json.dumps(monitoring), encoding="utf-8")
    expected = _incident_contract_revision_sha256(
        json.loads(CONTRACT_PATH.read_text(encoding="utf-8")),
        monitoring_path=monitoring_path,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 0
    assert f"Contract revision SHA-256: {expected}" in capsys.readouterr().out


def test_cli_rejects_incomplete_selected_monitoring_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    canonical = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    monitoring_path.write_text(json.dumps({"alerts": canonical["alerts"]}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 1
    output = capsys.readouterr().out
    assert "monitoring contract fields do not match the governed schema" in output
    assert "metrics must be a non-empty list" in output


def test_cli_rejects_selected_monitoring_alert_without_trigger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    payload = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    alert = next(item for item in payload["alerts"] if item["alert_id"] == "lotus-risk-http-5xx")
    alert.pop("query")
    alert.pop("condition")
    monitoring_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 1
    output = capsys.readouterr().out
    assert "alert fields do not match the governed schema" in output
    assert "alert query must be a nonblank string" in output
    assert "alert condition must be a nonblank string" in output


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("type", "gauge", "metric type does not match implementation"),
        ("source", "app.observability.missing", "metric source does not match implementation"),
    ],
)
def test_cli_rejects_selected_monitoring_metric_definition_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: str,
    expected: str,
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    payload = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    metric = next(item for item in payload["metrics"] if item["name"] == "http_requests_total")
    metric[field] = value
    monitoring_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 1
    assert expected in capsys.readouterr().out


def test_cli_rejects_duplicate_selected_monitoring_metric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    payload = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    metric = next(item for item in payload["metrics"] if item["name"] == "http_requests_total")
    duplicate = json.loads(json.dumps(metric))
    duplicate["labels"]["status"].remove("5xx")
    payload["metrics"].append(duplicate)
    monitoring_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 1
    assert "metric name must be unique" in capsys.readouterr().out


def test_cli_rejects_incomplete_runtime_metric_value_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    payload = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    metric = next(item for item in payload["metrics"] if item["name"] == "http_requests_total")
    metric["labels"]["method"].remove("GET")
    monitoring_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 1
    assert (
        "metric label value allowlists do not match runtime vocabularies" in capsys.readouterr().out
    )


def test_cli_rejects_query_borrowed_from_another_alert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    payload = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    alerts = {item["alert_id"]: item for item in payload["alerts"]}
    alerts["lotus-risk-http-5xx"]["query"] = alerts["lotus-risk-upstream-dependency-failures"][
        "query"
    ]
    monitoring_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 1
    assert "alert trigger does not match" in capsys.readouterr().out


def test_cli_rejects_alert_selector_outside_metric_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monitoring_path = tmp_path / "monitoring.json"
    payload = json.loads(
        (REPO_ROOT / "contracts/observability/lotus-risk-monitoring.v1.json").read_text(
            encoding="utf-8"
        )
    )
    metric = next(item for item in payload["metrics"] if item["name"] == "http_requests_total")
    metric["labels"]["status"].remove("5xx")
    monitoring_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_incident_response_contract.py",
            "--monitoring-contract",
            str(monitoring_path),
            "--prepare-exercise-revision",
        ],
    )

    assert main() == 1
    assert "selector status='5xx' is outside the metric allowlist" in capsys.readouterr().out


def test_exercise_result_digest_must_match_referenced_artifact(tmp_path: Path) -> None:
    artifact_reference, _ = _write_evidence_artifact(tmp_path)
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
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
                "executed_at": "2026-10-03T04:30:00Z",
                "outcome": "passed",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_artifact_reference": artifact_reference,
                "evidence_digest": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        repository_root=tmp_path,
    )

    assert any("artifact digest does not match" in issue for issue in issues)
    assert any("requires at least one valid passing" in issue for issue in issues)

    artifact_path = tmp_path / artifact_reference
    artifact_path.write_text(
        json.dumps(
            {
                "alert_id": "lotus-risk-upstream-dependency-failures",
                "bounded_correlation_reference": "client-alice-0123456789abcdef",
                "release_sha": "client-PB001-credential-secret",
            }
        ),
        encoding="utf-8",
    )
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["evidence_digest"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    unsafe_issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        expected_evidence_fields={
            "lotus-risk-http-5xx": {
                "alert_id",
                "bounded_correlation_reference",
                "deployment_event_reference",
                "exercise_id",
                "image_digest",
                "reconciliation_result",
                "release_sha",
                "timestamp_utc",
            }
        },
        repository_root=tmp_path,
    )

    assert any("release_sha is not source-safe" in issue for issue in unsafe_issues)
    assert any(
        "bounded_correlation_reference is not source-safe" in issue for issue in unsafe_issues
    )
    assert any("alert_id does not match scenario" in issue for issue in unsafe_issues)
    assert any("fields do not match response profile" in issue for issue in unsafe_issues)

    bad_reference = (
        "evidence/incident-response-exercises/artifacts/client-PB001-credential-secret.json"
    )
    bad_path = tmp_path / bad_reference
    bad_path.write_bytes(artifact_path.read_bytes())
    payload["evidence_artifact_reference"] = bad_reference
    payload["evidence_digest"] = hashlib.sha256(bad_path.read_bytes()).hexdigest()
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    filename_issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        repository_root=tmp_path,
    )
    assert any("filename must be a bounded opaque identifier" in issue for issue in filename_issues)


def test_passed_exercise_rejects_failed_reconciliation(tmp_path: Path) -> None:
    artifact_reference = (
        "evidence/incident-response-exercises/artifacts/evidence-0123456789abcdef.json"
    )
    artifact_path = tmp_path / artifact_reference
    artifact_path.parent.mkdir(parents=True)
    artifact_fields = {
        "alert_id": "lotus-risk-endpoint-failure-rate",
        "bounded_correlation_reference": "correlation-0123456789abcdef",
        "exercise_id": "exercise-0123456789abcdef",
        "reconciliation_result": "failed",
        "release_sha": "0" * 40,
        "timestamp_utc": "2026-10-03T04:30:00Z",
    }
    artifact_path.write_text(json.dumps(artifact_fields), encoding="utf-8")
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_result",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2026-10-03T05:00:00Z",
                "scenario_alert_id": "lotus-risk-endpoint-failure-rate",
                "owner_roles": ["service_support_owner"],
                "executed_at": "2026-10-03T04:30:00Z",
                "outcome": "passed",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_artifact_reference": artifact_reference,
                "evidence_digest": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        expected_evidence_fields={"lotus-risk-endpoint-failure-rate": set(artifact_fields)},
        repository_root=tmp_path,
    )

    assert any("cannot preserve a failed reconciliation" in issue for issue in issues)
    assert any("requires at least one valid passing" in issue for issue in issues)


def test_escalation_roles_must_be_unique(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    payload["escalation_model"]["roles"].append("incident_commander")
    contract_path = tmp_path / "incident.json"
    contract_path.write_text(json.dumps(payload), encoding="utf-8")

    issues = validate_incident_response_contract(contract_path)

    assert any("escalation roles do not match" in issue for issue in issues)


def test_exercise_plan_rejects_stale_revision_and_elapsed_schedule(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "artifact_version": "1.0.0",
                "contract_id": "lotus-risk:incident-response:v1",
                "evidence_type": "exercise_plan",
                "exercise_id": "exercise-0123456789abcdef",
                "recorded_at": "2020-01-01T00:00:00Z",
                "scenario_alert_id": "lotus-risk-http-5xx",
                "owner_roles": ["incident_commander"],
                "scheduled_for": "2020-01-02T00:00:00Z",
                "contract_revision_sha256": "0" * 64,
                "response_profiles_sha256": "1" * 64,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "planned",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        expected_contract_revision_sha256=CONTRACT_REVISION_SHA256,
        repository_root=tmp_path,
    )

    assert any("scheduled_for has elapsed" in issue for issue in issues)
    assert any("contract revision does not match" in issue for issue in issues)
    assert any("response profile revision does not match" in issue for issue in issues)


def test_exercise_plan_requires_selected_alert_roles(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
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
                "owner_roles": ["source_service_owner"],
                "scheduled_for": "2099-10-10T05:00:00Z",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "planned",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        expected_alert_roles={
            "lotus-risk-http-5xx": {
                "incident_commander",
                "service_support_owner",
                "platform_operations_owner",
            }
        },
        repository_root=tmp_path,
    )

    assert any("owner_roles do not cover" in issue for issue in issues)


def test_passed_exercise_requires_selected_alert_roles(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence/incident-response-exercises/exercise-0123456789abcdef.json"
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
                "owner_roles": ["source_service_owner"],
                "executed_at": "2026-10-03T04:30:00Z",
                "outcome": "passed",
                "contract_revision_sha256": CONTRACT_REVISION_SHA256,
                "response_profiles_sha256": GOVERNED_RESPONSE_PROFILES_SHA256,
                "evidence_digest": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        expected_alert_roles={
            "lotus-risk-http-5xx": {
                "incident_commander",
                "service_support_owner",
                "platform_operations_owner",
            }
        },
        repository_root=tmp_path,
    )

    assert any("owner_roles do not cover" in issue for issue in issues)
    assert any("requires at least one valid passing" in issue for issue in issues)

    artifact = json.loads(evidence.read_text(encoding="utf-8"))
    artifact["outcome"] = "failed"
    artifact["owner_roles"] = [
        "incident_commander",
        "service_support_owner",
        "platform_operations_owner",
    ]
    evidence.write_text(json.dumps(artifact), encoding="utf-8")
    failed_only_issues = _validate_exercise_evidence_references(
        "exercised",
        ["evidence/incident-response-exercises/exercise-0123456789abcdef.json"],
        repository_root=tmp_path,
    )

    assert any("requires at least one valid passing" in issue for issue in failed_only_issues)
