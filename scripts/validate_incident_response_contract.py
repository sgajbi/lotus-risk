from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from scripts.validate_observability_contracts import (
    validate_observability_contract,
)

CONTRACT_PATH = ROOT / "contracts" / "observability" / "lotus-risk-incident-response.v1.json"
MONITORING_PATH = ROOT / "contracts" / "observability" / "lotus-risk-monitoring.v1.json"
CANONICAL_INCIDENT_RUNBOOK = "docs/runbooks/incident-response.md"
CANONICAL_MONITORING_CONTRACT = Path("contracts/observability/lotus-risk-monitoring.v1.json")
MAX_EVIDENCE_CLOCK_SKEW = timedelta(minutes=5)
CONTRACT_FIELDS = {
    "alert_responses",
    "contract_id",
    "contract_version",
    "corrective_action_model",
    "credential_response",
    "deployment_blockers",
    "escalation_model",
    "exercise_evidence",
    "incident_runbook",
    "owner_repository",
    "production_acceptance",
    "service",
    "severity_model",
    "source_safe_evidence_fields",
    "status",
}
ESCALATION_FIELDS = {"assignment_status", "contact_source", "roles"}
CREDENTIAL_RESPONSE_FIELDS = {
    "actions",
    "owner",
    "repository_secret_material_permitted",
}
EXERCISE_FIELDS = {"evidence_references", "production_claim", "status"}
CORRECTIVE_ACTION_FIELDS = {"allowed_statuses", "required_fields"}

ALLOWED_SEVERITIES = {"SEV1", "SEV2"}
GOVERNED_SEVERITY_MEANINGS = {
    "SEV1": "Critical service, security, or data incident requiring incident command and immediate containment.",
    "SEV2": "Material degradation requiring service-owner investigation and bounded remediation.",
}
ALLOWED_MONITORING_SEVERITIES = {"warning", "critical"}
GOVERNED_ALERT_IDS = {
    "lotus-risk-calculation-supportability-degraded",
    "lotus-risk-endpoint-failure-rate",
    "lotus-risk-http-5xx",
    "lotus-risk-scenario-job-retryable-error",
    "lotus-risk-upstream-dependency-failures",
}
GOVERNED_ALERT_SEVERITIES = {
    "lotus-risk-calculation-supportability-degraded": ("warning", "SEV2"),
    "lotus-risk-endpoint-failure-rate": ("warning", "SEV2"),
    "lotus-risk-http-5xx": ("critical", "SEV1"),
    "lotus-risk-scenario-job-retryable-error": ("warning", "SEV2"),
    "lotus-risk-upstream-dependency-failures": ("critical", "SEV1"),
}
GOVERNED_RESPONSE_PROFILES_SHA256 = (
    "69d6f24c6aa930cc9d26313ae0e8a72704f06fd988c8c183fe81ddb79c52b579"
)
ALLOWED_ROLES = {
    "incident_commander",
    "platform_operations_owner",
    "security_response_owner",
    "service_support_owner",
    "source_service_owner",
}
ALLOWED_EVIDENCE_FIELDS = {
    "alert_id",
    "bounded_correlation_reference",
    "corrective_action_id",
    "deployment_event_reference",
    "exercise_id",
    "image_digest",
    "metric_snapshot_digest",
    "reconciliation_result",
    "release_sha",
    "timestamp_utc",
}
ALLOWED_EXERCISE_STATUSES = {"not_exercised", "planned", "exercised"}
ALLOWED_ACTION_STATUSES = {"open", "in_progress", "verified", "accepted_external_blocker"}
GOVERNED_CONTRACT_STATUSES = {"prepared_not_exercised", "exercise_planned", "exercised"}
EXERCISE_EVIDENCE_BLOCKER = "executed incident exercise or incident-review evidence"
BASE_DEPLOYMENT_BLOCKERS = {
    "approved contact-directory assignments",
    "deployed alert routing and acknowledgement targets",
    "deployment-owned corrective-action tracker",
    "production acceptance by the incident commander and service support owner",
}
LIFECYCLE_POINTER_DOCUMENTS = (
    Path("REPOSITORY-ENGINEERING-CONTEXT.md"),
    Path("docs/observability.md"),
    Path("wiki/Operations-Runbook.md"),
)
EXERCISE_EVIDENCE_ROOT = Path("evidence/incident-response-exercises")
REQUIRED_ACTION_FIELDS = {
    "corrective_action_id",
    "owner_role",
    "status",
    "due_date",
    "verification_reference",
}
REQUIRED_CREDENTIAL_ACTIONS = {
    "revoke_compromised_identity",
    "rotate_credential",
    "verify_revocation",
    "revalidate_service_identity",
}


class DuplicateJsonKeyError(ValueError):
    pass


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise DuplicateJsonKeyError(key)
        payload[key] = value
    return payload


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_json_object,
    )
    if not isinstance(payload, dict):
        raise TypeError(f"{path}: contract root must be an object")
    return payload


def _repository_path(reference: str, *, repository_root: Path = ROOT) -> Path | None:
    relative_path = Path(reference)
    if relative_path.is_absolute() or re.match(r"^(?:[A-Za-z]:[\\/]|[\\/])", reference):
        return None
    root = repository_root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _markdown_anchor_exists(reference: str, *, repository_root: Path = ROOT) -> bool:
    path_text, separator, anchor = reference.partition("#")
    if not separator or not anchor:
        return False
    path = _repository_path(path_text, repository_root=repository_root)
    if path is None or not path.is_file():
        return False
    headings = {
        re.sub(r"\s+", "-", re.sub(r"[^a-z0-9 -]", "", line.lstrip("#").strip().lower()))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }
    return anchor in headings


def _non_empty_strings(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _is_nonblank_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_utc_timestamp(value: object) -> datetime | None:
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
            value,
        )
        is None
    ):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is UTC else None


def _matches_unique_string_set(value: object, expected: set[str]) -> bool:
    return (
        isinstance(value, list)
        and all(_is_nonblank_string(item) for item in value)
        and len(value) == len(set(value))
        and set(value) == expected
    )


def _incident_contract_revision_sha256(
    contract: dict[str, Any],
    *,
    monitoring_path: Path | None = None,
    repository_root: Path = ROOT,
) -> str:
    lifecycle_fields = {
        "deployment_blockers",
        "exercise_evidence",
        "production_acceptance",
        "status",
    }
    governed_behavior = {
        field: value for field, value in contract.items() if field not in lifecycle_fields
    }
    runbook_reference = contract.get("incident_runbook")
    runbook_path = (
        _repository_path(runbook_reference, repository_root=repository_root)
        if isinstance(runbook_reference, str)
        else None
    )
    governed_runbook = ""
    if runbook_path is not None and runbook_path.is_file():
        governed_runbook = runbook_path.read_text(encoding="utf-8")
        governed_runbook = re.sub(
            r"^\s*-\s*Contract posture:\s*`(?:prepared_not_exercised|exercise_planned|exercised)`\s*\n?",
            "",
            governed_runbook,
            flags=re.MULTILINE,
        )
        governed_runbook = re.sub(
            r"^\s*-\s*Production acceptance:\s*`(?:true|false)`\s*\n?",
            "",
            governed_runbook,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    governed_behavior["incident_runbook_sha256"] = hashlib.sha256(
        governed_runbook.encode()
    ).hexdigest()
    resolved_monitoring_path = monitoring_path or repository_root / CANONICAL_MONITORING_CONTRACT
    governed_behavior["monitoring_contract_sha256"] = ""
    if resolved_monitoring_path.is_file():
        monitoring_contract = _load_object(resolved_monitoring_path)
        governed_behavior["monitoring_contract_sha256"] = hashlib.sha256(
            json.dumps(monitoring_contract, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    return hashlib.sha256(
        json.dumps(governed_behavior, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _response_profiles_sha256(contract: dict[str, Any]) -> str:
    responses = contract.get("alert_responses")
    if not isinstance(responses, list):
        return ""
    response_profiles = {
        response["alert_id"]: {
            field: value for field, value in response.items() if field != "alert_id"
        }
        for response in responses
        if isinstance(response, dict) and response.get("alert_id") in GOVERNED_ALERT_IDS
    }
    return hashlib.sha256(
        json.dumps(response_profiles, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _declared_contract_statuses(text: str) -> set[str]:
    return set(
        re.findall(
            r"^\s*(?:-\s*)?(?:(?:[^.!?\n]*,\s*)|(?:it is true that\s+))?"
            r"(?:the\s+)?(?:contract posture\s*(?::|is)\s*`?|"
            r"(?:contract|repository proof)\s+"
            r"(?:(?:is|remains|status (?:is|remains))\s+(?:(?:now|already|currently)\s+)?`?|"
            r"has\s+(?:(?:already|now|currently)\s+)?been\s+(?:(?:now|currently)\s+)?`?|"
            r"status\s*:\s*`?))"
            r"(prepared_not_exercised|exercise_planned|exercised)`?[.!]?\s*$",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
    )


_NEGATION_CONTRACTIONS = {
    "aren't": "are not",
    "can't": "can not",
    "couldn't": "could not",
    "didn't": "did not",
    "doesn't": "does not",
    "don't": "do not",
    "hadn't": "had not",
    "hasn't": "has not",
    "haven't": "have not",
    "isn't": "is not",
    "mustn't": "must not",
    "shan't": "shall not",
    "shouldn't": "should not",
    "wasn't": "was not",
    "weren't": "were not",
    "won't": "will not",
    "wouldn't": "would not",
}
_NEGATION_CONTRACTION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(value) for value in _NEGATION_CONTRACTIONS) + r")\b",
    re.IGNORECASE,
)


def _expand_negation_contractions(text: str) -> str:
    normalized = text.replace("’", "'")
    return _NEGATION_CONTRACTION_PATTERN.sub(
        lambda match: _NEGATION_CONTRACTIONS[match.group(0).lower()], normalized
    )


def _denied_contract_statuses(text: str) -> set[str]:
    return set(
        re.findall(
            r"^\s*(?:-\s*)?(?:"
            r"(?:it|this)\s+(?:is|was)\s+(?:false|not\s+true)\s+that\s+"
            r"(?:the\s+)?(?:contract posture|contract status|contract|repository proof)\s+"
            r"(?:(?::|is|was|remains|status (?:is|was|remains))\s+|"
            r"has\s+(?:(?:now|already|currently)\s+)?been\s+"
            r"(?:(?:now|already|currently)\s+)?)|"
            r"(?:the\s+)?(?:contract posture|contract status|contract|repository proof)\s+"
            r"(?::|is|was|remains|status (?:is|was|remains))\s+"
            r"(?:(?:now|already|currently)\s+)?(?:not|no\s+longer)\s+|"
            r"(?:the\s+)?(?:contract posture|contract status|contract|repository proof)\s+has\s+"
            r"(?:(?:now|already|currently)\s+)?(?:not|never|no\s+longer)\s+been\s+)"
            r"`?(prepared_not_exercised|exercise_planned|exercised)`?[.!]?\s*$",
            _expand_negation_contractions(text),
            re.IGNORECASE | re.MULTILINE,
        )
    )


def _validate_evidence_artifact(
    reference: object,
    digest: object,
    scenario_alert_id: object,
    outcome: object,
    exercise_id: object,
    executed_at: object,
    expected_fields: set[str] | None,
    *,
    repository_root: Path,
) -> list[str]:
    if not _is_nonblank_string(reference):
        return ["exercise result evidence_artifact_reference must be a nonblank string"]
    assert isinstance(reference, str)
    path = _repository_path(reference, repository_root=repository_root)
    artifact_root = (repository_root / EXERCISE_EVIDENCE_ROOT / "artifacts").resolve()
    if path is None:
        return [f"{reference}: exercise evidence artifact must resolve inside the repository"]
    try:
        path.relative_to(artifact_root)
    except ValueError:
        return [
            f"{reference}: exercise evidence artifact must use {artifact_root.relative_to(repository_root).as_posix()}"
        ]
    canonical_reference = path.relative_to(repository_root.resolve()).as_posix()
    if reference != canonical_reference or path.parent != artifact_root:
        return [f"{reference}: exercise evidence artifact must use its canonical direct-child path"]
    if path.suffix != ".json" or not path.is_file():
        return [f"{reference}: exercise evidence artifact JSON does not exist"]
    if re.fullmatch(r"evidence-[0-9a-f]{16}\.json", path.name) is None:
        return [
            f"{reference}: exercise evidence artifact filename must be a bounded opaque identifier"
        ]
    try:
        artifact = _load_object(path)
    except DuplicateJsonKeyError:
        return [f"{reference}: duplicate JSON object keys are forbidden"]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return [f"{reference}: exercise evidence artifact must be a JSON object"]
    issues: list[str] = []
    if not artifact or not set(artifact) <= ALLOWED_EVIDENCE_FIELDS:
        issues.append(f"{reference}: exercise evidence artifact fields are not source-safe")
    if expected_fields is not None and set(artifact) != expected_fields:
        issues.append(
            f"{reference}: exercise evidence artifact fields do not match response profile"
        )
    if any(not _is_nonblank_string(value) for value in artifact.values()):
        issues.append(f"{reference}: exercise evidence artifact values must be nonblank strings")
    if artifact.get("alert_id") != scenario_alert_id:
        issues.append(f"{reference}: exercise evidence artifact alert_id does not match scenario")
    if artifact.get("exercise_id") != exercise_id:
        issues.append(f"{reference}: exercise evidence artifact exercise_id does not match result")
    if artifact.get("timestamp_utc") != executed_at:
        issues.append(f"{reference}: exercise evidence artifact timestamp does not match result")
    hex_digest = re.compile(r"[0-9a-f]{64}")
    field_patterns = {
        "bounded_correlation_reference": re.compile(r"correlation-[0-9a-f]{16}"),
        "corrective_action_id": re.compile(r"corrective-action-[0-9a-f]{16}"),
        "deployment_event_reference": re.compile(r"deployment-event-[0-9a-f]{16}"),
        "exercise_id": re.compile(r"exercise-[0-9a-f]{16}"),
        "image_digest": re.compile(r"sha256:[0-9a-f]{64}"),
        "metric_snapshot_digest": hex_digest,
        "release_sha": re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}"),
        "timestamp_utc": re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"),
    }
    for field, pattern in field_patterns.items():
        if field in artifact and pattern.fullmatch(str(artifact[field])) is None:
            issues.append(f"{reference}: exercise evidence artifact {field} is not source-safe")
    if "reconciliation_result" in artifact and artifact["reconciliation_result"] not in {
        "failed",
        "passed",
    }:
        issues.append(f"{reference}: exercise evidence artifact reconciliation_result is invalid")
    if outcome == "passed" and artifact.get("reconciliation_result") == "failed":
        issues.append(f"{reference}: passed exercise cannot preserve a failed reconciliation")
    if not isinstance(digest, str) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        issues.append(f"{reference}: exercise evidence artifact digest does not match")
    return issues


def _declared_production_acceptance(
    text: str, *, reject_unsupported_claims: bool = False
) -> list[str]:
    declarations: list[str] = []
    normalized_text = re.sub(
        r"production\s+acceptance",
        "production acceptance",
        text,
        flags=re.IGNORECASE,
    )
    for sentence in normalized_text.splitlines():
        if re.search(r"production acceptance", sentence, re.IGNORECASE) is None:
            continue
        if re.match(
            r"\s*(?:-\s*)?(?:(?:for\s+)?example\b|"
            r"configuration\s+(?:example|fragment)\b)",
            sentence,
            re.IGNORECASE,
        ):
            continue
        match = re.fullmatch(
            r"\s*(?:-\s*)?(?:[^.!?`]*,\s*)?production acceptance\s*"
            r"(?::|is|remains)\s*`?(true|false)`?[.!]?\s*",
            sentence,
            re.IGNORECASE,
        )
        if match is not None:
            declarations.append(match.group(1).lower())
        elif reject_unsupported_claims:
            declarations.append("unsupported_claim")
    return declarations


def _contains_affirmative_mapping(
    clause: str,
    direct_patterns: tuple[str, ...],
    imperative_patterns: tuple[str, ...],
) -> bool:
    negation = re.compile(
        r"\b(?:"
        r"(?:no|not|never|neither|nor)(?:\s+(?:all|any|both|each|either|every|the|these|those))?"
        r"|none\s+of(?:\s+the)?"
        r"|(?:it|this)\s+(?:is|was)\s+(?:false|not\s+true)\s+that"
        r"|(?:do|does|did|must|should|shall|will|may|can|could|would)\s+not"
        r")\s*$",
        re.IGNORECASE,
    )
    return any(
        negation.search(clause[: match.start()]) is None
        for pattern in direct_patterns + imperative_patterns
        for match in re.finditer(pattern, clause, re.IGNORECASE)
    )


def _contains_denied_governed_mapping(
    clause: str,
    direct_patterns: tuple[str, ...],
    imperative_patterns: tuple[str, ...],
    internally_negated_patterns: tuple[str, ...],
) -> bool:
    negation = re.compile(
        r"\b(?:"
        r"(?:no|not|never|neither|nor)(?:\s+(?:all|any|both|each|either|every|the|these|those))?"
        r"|none\s+of(?:\s+the)?"
        r"|(?:it|this)\s+(?:is|was)\s+(?:false|not\s+true)\s+that"
        r"|(?:do|does|did|must|should|shall|will|may|can|could|would)\s+not"
        r")\s*$",
        re.IGNORECASE,
    )
    for pattern in direct_patterns + imperative_patterns:
        for match in re.finditer(pattern, clause, re.IGNORECASE):
            claim = match.group(0)
            governed_pair = (
                re.search(r"\bcritical\b", claim, re.IGNORECASE) is not None
                and re.search(r"\bSEV1\b", claim, re.IGNORECASE) is not None
            ) or (
                re.search(r"\bwarning", claim, re.IGNORECASE) is not None
                and re.search(r"\bSEV2\b", claim, re.IGNORECASE) is not None
            )
            if governed_pair and negation.search(clause[: match.start()]) is not None:
                return True
    return any(
        re.search(pattern, clause, re.IGNORECASE) is not None
        for pattern in internally_negated_patterns
    )


def _validate_incident_runbook(
    reference: object,
    *,
    contract_status: object,
    production_acceptance: object,
    repository_root: Path = ROOT,
) -> list[str]:
    if not isinstance(reference, str):
        return ["incident_runbook must be a repository-relative path"]
    path = _repository_path(reference, repository_root=repository_root)
    if path is None:
        return ["incident_runbook must remain inside the repository"]
    if not path.is_file():
        return [f"{reference}: incident runbook does not exist"]
    text = path.read_text(encoding="utf-8")
    required_terms = (
        "contracts/observability/lotus-risk-incident-response.v1.json",
        "make incident-response-contract-validate",
        "## Declare And Contain",
        "## Evidence And Communication",
        "## Recover And Reconcile",
        "## Acceptance Boundary",
    )
    issues = [
        f"{reference}: missing required incident term {term!r}"
        for term in required_terms
        if term not in text
    ]
    documented_status = re.search(r"^- Contract posture: `([^`]+)`$", text, re.MULTILINE)
    if documented_status is None or documented_status.group(1) != contract_status:
        issues.append(f"{reference}: documented contract posture does not match contract status")
    asserted_statuses = _declared_contract_statuses(text)
    if asserted_statuses != {contract_status} or contract_status in _denied_contract_statuses(text):
        issues.append(f"{reference}: contains a stale or missing contract posture assertion")
    expected_acceptance = str(production_acceptance).lower()
    documented_acceptance = _declared_production_acceptance(text, reject_unsupported_claims=True)
    if documented_acceptance != [expected_acceptance]:
        issues.append(f"{reference}: documented production acceptance does not match contract")
    documented_severity_mapping = re.findall(
        r"^\s*(?:-\s*)?Monitoring severity mapping:\s*`?"
        r"(critical=SEV[12],warning=SEV[12])`?\s*$",
        text,
        re.MULTILINE,
    )
    if documented_severity_mapping != ["critical=SEV1,warning=SEV2"]:
        issues.append(f"{reference}: documented severity mapping does not match contract")
    text_without_declaration = re.sub(
        r"^\s*(?:-\s*)?Monitoring severity mapping:\s*`?"
        r"critical=SEV1,warning=SEV2`?\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    normalized_guidance = re.sub(
        r"\s+", " ", _expand_negation_contractions(text_without_declaration)
    )
    alert_term = (
        r"(?:critical(?:(?:\s+monitoring)?\s+alerts?)?|"
        r"warnings?(?:(?:\s+monitoring)?\s+alerts?)?)"
    )
    severity_term = r"`?SEV[12]`?"
    modal = r"(?:(?:should|must|shall|will|may|can|could|would)\s+)?"
    state_adverb = r"(?:(?:now|currently|already)\s+)?"
    copula = rf"(?:are|is|was|were|be|remain|remains)\s+{state_adverb}"
    linked_verb = (
        r"(?:map(?:s|ped)?\s+to|classif(?:y|ies|ied)\s+as|"
        r"assign(?:s|ed)?\s+to|correspond(?:s|ed)?\s+to|"
        r"appl(?:y|ies|ied)\s+to|designat(?:e|es|ed)\s+as|"
        r"treat(?:s|ed)?\s+as|equat(?:e|es|ed)\s+(?:to|with)|means?)"
    )
    infix_relation = (
        rf"(?:=|{modal}{copula}|"
        rf"{modal}(?:{copula})?{linked_verb}|"
        rf"{modal}(?:has|have)\s+(?:a\s+)?severity(?:\s+of)?)"
    )
    imperative = r"(?:map|classify|assign|categorize|designate|treat)"
    determiner = r"(?:(?:all|any|both|each|either|every|neither|the|these|those)\s+)?"
    direct_patterns = (
        rf"\b{alert_term}\s+{infix_relation}\s*{severity_term}\b",
        rf"{severity_term}\s+{infix_relation}\s*\b{alert_term}\b",
        rf"\b(?:are|is)\s+{state_adverb}{alert_term}\s+{severity_term}\b",
    )
    imperative_patterns = (
        rf"\b{imperative}\s+{determiner}{alert_term}\s+(?:to|as)\s+{severity_term}\b",
        rf"\b{imperative}\s+{determiner}{severity_term}\s+(?:to|as)\s+{alert_term}\b",
        rf"\bset\s+(?:the\s+)?severity\s+of\s+{alert_term}\s+to\s+{severity_term}\b",
        rf"\bset\s+(?:the\s+)?severity\s+of\s+{severity_term}\s+to\s+{alert_term}\b",
    )
    internally_negated_patterns = (
        rf"\bcritical(?:(?:\s+monitoring)?\s+alerts?)?\s+{infix_relation}\s*(?:not|never|no\s+longer)\s+`?SEV1`?\b",
        rf"\bwarnings?(?:(?:\s+monitoring)?\s+alerts?)?\s+{infix_relation}\s*(?:not|never|no\s+longer)\s+`?SEV2`?\b",
        rf"\b`?SEV1`?\s+no\s+longer\s+{linked_verb}\s+critical(?:(?:\s+monitoring)?\s+alerts?)?\b",
        rf"\b`?SEV2`?\s+no\s+longer\s+{linked_verb}\s+warnings?(?:(?:\s+monitoring)?\s+alerts?)?\b",
        rf"\b`?SEV1`?\s+never\s+{linked_verb}\s+critical(?:(?:\s+monitoring)?\s+alerts?)?\b",
        rf"\b`?SEV2`?\s+never\s+{linked_verb}\s+warnings?(?:(?:\s+monitoring)?\s+alerts?)?\b",
        rf"\b`?SEV1`?\s+(?:does|did|should|must|shall|will|may|can|could|would)\s+not\s+{linked_verb}\s+critical(?:(?:\s+monitoring)?\s+alerts?)?\b",
        rf"\b`?SEV2`?\s+(?:does|did|should|must|shall|will|may|can|could|would)\s+not\s+{linked_verb}\s+warnings?(?:(?:\s+monitoring)?\s+alerts?)?\b",
        rf"\bcritical(?:(?:\s+monitoring)?\s+alerts?)?\s+(?:do|does|did|should|must|shall|will|may|can|could|would)\s+not\s+{linked_verb}\s+`?SEV1`?\b",
        rf"\bwarnings?(?:(?:\s+monitoring)?\s+alerts?)?\s+(?:do|does|did|should|must|shall|will|may|can|could|would)\s+not\s+{linked_verb}\s+`?SEV2`?\b",
    )
    if any(
        _contains_affirmative_mapping(clause, direct_patterns, imperative_patterns)
        or _contains_denied_governed_mapping(
            clause,
            direct_patterns,
            imperative_patterns,
            internally_negated_patterns,
        )
        for clause in re.split(r"[.!?;]", normalized_guidance)
    ):
        issues.append(f"{reference}: duplicates operational severity guidance")
    return issues


def _validate_exercise_evidence_references(
    status: str | None,
    references: object,
    *,
    expected_contract_revision_sha256: str | None = None,
    expected_alert_roles: dict[str, set[str]] | None = None,
    expected_evidence_fields: dict[str, set[str]] | None = None,
    expected_response_profiles_sha256: str = GOVERNED_RESPONSE_PROFILES_SHA256,
    repository_root: Path = ROOT,
) -> list[str]:
    if not isinstance(references, list) or not _non_empty_strings(references):
        if references == []:
            if status in {"planned", "exercised"}:
                return [f"{status} status requires evidence references"]
            return []
        return ["exercise evidence references must be nonblank strings"]
    if len(references) != len(set(references)):
        return ["exercise evidence references must be unique"]
    if status == "not_exercised":
        return ["not_exercised status must not carry exercise evidence"]

    issues: list[str] = []
    evidence_root = (repository_root / EXERCISE_EVIDENCE_ROOT).resolve()
    expected_type = "exercise_plan" if status == "planned" else "exercise_result"
    latest_credible_time = datetime.now(UTC) + MAX_EVIDENCE_CLOCK_SKEW
    has_valid_passing_result = False
    for reference in references:
        path = _repository_path(reference, repository_root=repository_root)
        if path is None:
            issues.append(f"{reference}: exercise evidence must resolve inside the repository")
            continue
        try:
            path.relative_to(evidence_root)
        except ValueError:
            issues.append(
                f"{reference}: exercise evidence must use {EXERCISE_EVIDENCE_ROOT.as_posix()}"
            )
            continue
        if path.parent != evidence_root:
            issues.append(f"{reference}: exercise evidence must be a direct governed child")
            continue
        canonical_reference = (EXERCISE_EVIDENCE_ROOT / path.name).as_posix()
        if reference != canonical_reference:
            issues.append(
                f"{reference}: exercise evidence reference must equal the canonical direct-child path"
            )
            continue
        if path.suffix != ".json" or not path.is_file():
            issues.append(f"{reference}: exercise evidence JSON does not exist")
            continue
        try:
            artifact = _load_object(path)
        except DuplicateJsonKeyError:
            issues.append(f"{reference}: duplicate JSON object keys are forbidden")
            continue
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            issues.append(f"{reference}: exercise evidence must be a JSON object")
            continue
        artifact_issue_count = len(issues)
        if artifact.get("artifact_version") != "1.0.0":
            issues.append(f"{reference}: exercise evidence version must be 1.0.0")
        if artifact.get("contract_id") != "lotus-risk:incident-response:v1":
            issues.append(f"{reference}: exercise evidence contract_id does not match")
        if artifact.get("evidence_type") != expected_type:
            issues.append(f"{reference}: exercise evidence type must be {expected_type}")
        common_fields = {
            "artifact_version",
            "contract_id",
            "evidence_type",
            "exercise_id",
            "owner_roles",
            "recorded_at",
            "scenario_alert_id",
        }
        lifecycle_fields = (
            {"contract_revision_sha256", "response_profiles_sha256", "scheduled_for"}
            if status == "planned"
            else {
                "contract_revision_sha256",
                "evidence_artifact_reference",
                "evidence_digest",
                "executed_at",
                "outcome",
                "response_profiles_sha256",
            }
        )
        expected_fields = common_fields | lifecycle_fields
        if set(artifact) != expected_fields:
            issues.append(
                f"{reference}: exercise evidence fields do not match the governed schema: "
                f"missing={sorted(expected_fields - set(artifact))}, "
                f"extra={sorted(set(artifact) - expected_fields)}"
            )
        exercise_id = artifact.get("exercise_id")
        if (
            not isinstance(exercise_id, str)
            or re.fullmatch(r"exercise-[0-9a-f]{16}", exercise_id) is None
        ):
            issues.append(f"{reference}: exercise_id must be a bounded opaque identifier")
        elif path.stem != exercise_id:
            issues.append(f"{reference}: filename must equal the opaque exercise_id")
        recorded_at = _parse_utc_timestamp(artifact.get("recorded_at"))
        if recorded_at is None:
            issues.append(f"{reference}: recorded_at must be a UTC timestamp")
        elif recorded_at > latest_credible_time:
            issues.append(f"{reference}: recorded_at exceeds the bounded current-time skew")
        if artifact.get("scenario_alert_id") not in GOVERNED_ALERT_IDS:
            issues.append(f"{reference}: scenario_alert_id must be a governed alert")
        owner_roles = artifact.get("owner_roles")
        if (
            not isinstance(owner_roles, list)
            or not _non_empty_strings(owner_roles)
            or len(owner_roles) != len(set(owner_roles))
            or not set(owner_roles) <= ALLOWED_ROLES
        ):
            issues.append(f"{reference}: owner_roles must be unique governed roles")
        requires_role_coverage = status == "planned" or artifact.get("outcome") == "passed"
        if requires_role_coverage and expected_alert_roles is not None:
            required_roles = expected_alert_roles.get(str(artifact.get("scenario_alert_id")))
            if (
                required_roles is None
                or not isinstance(owner_roles, list)
                or not (required_roles <= set(owner_roles))
            ):
                issues.append(f"{reference}: owner_roles do not cover the alert response")
        if status == "planned":
            scheduled_for = _parse_utc_timestamp(artifact.get("scheduled_for"))
            if scheduled_for is None:
                issues.append(f"{reference}: scheduled_for must be a UTC timestamp")
            elif recorded_at is not None and scheduled_for < recorded_at:
                issues.append(f"{reference}: scheduled_for must not precede recorded_at")
            elif scheduled_for < datetime.now(UTC) - MAX_EVIDENCE_CLOCK_SKEW:
                issues.append(f"{reference}: scheduled_for has elapsed")
        else:
            executed_at = _parse_utc_timestamp(artifact.get("executed_at"))
            if executed_at is None:
                issues.append(f"{reference}: executed_at must be a UTC timestamp")
            elif executed_at > latest_credible_time:
                issues.append(f"{reference}: executed_at exceeds the bounded current-time skew")
            elif recorded_at is not None and executed_at > recorded_at:
                issues.append(f"{reference}: executed_at must not follow recorded_at")
            if artifact.get("outcome") not in {"passed", "failed"}:
                issues.append(f"{reference}: outcome must be passed or failed")
            evidence_digest = artifact.get("evidence_digest")
            if (
                not isinstance(evidence_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", evidence_digest) is None
            ):
                issues.append(f"{reference}: evidence_digest must be lowercase SHA-256")
            else:
                issues.extend(
                    _validate_evidence_artifact(
                        artifact.get("evidence_artifact_reference"),
                        evidence_digest,
                        artifact.get("scenario_alert_id"),
                        artifact.get("outcome"),
                        artifact.get("exercise_id"),
                        artifact.get("executed_at"),
                        (
                            expected_evidence_fields.get(str(artifact.get("scenario_alert_id")))
                            if expected_evidence_fields is not None
                            else None
                        ),
                        repository_root=repository_root,
                    )
                )
        contract_revision_sha256 = artifact.get("contract_revision_sha256")
        if (
            not isinstance(contract_revision_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", contract_revision_sha256) is None
        ):
            issues.append(f"{reference}: contract_revision_sha256 must be lowercase SHA-256")
        elif (
            expected_contract_revision_sha256 is not None
            and contract_revision_sha256 != expected_contract_revision_sha256
        ):
            issues.append(f"{reference}: contract revision does not match current contract")
        if artifact.get("response_profiles_sha256") != expected_response_profiles_sha256:
            issues.append(f"{reference}: response profile revision does not match current contract")
        if artifact.get("outcome") == "passed" and len(issues) == artifact_issue_count:
            has_valid_passing_result = True
    if status == "exercised" and not has_valid_passing_result:
        issues.append("exercised status requires at least one valid passing exercise result")
    return issues


def _validate_lifecycle_pointer_documents(repository_root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for relative_path in LIFECYCLE_POINTER_DOCUMENTS:
        path = repository_root / relative_path
        if not path.is_file():
            issues.append(f"{relative_path}: lifecycle pointer document does not exist")
            continue
        text = path.read_text(encoding="utf-8")
        if _declared_contract_statuses(text) or _declared_production_acceptance(text):
            issues.append(
                f"{relative_path}: duplicates lifecycle posture owned by the incident runbook"
            )
    return issues


def validate_incident_response_contract(
    contract_path: Path = CONTRACT_PATH,
    monitoring_path: Path = MONITORING_PATH,
    *,
    enforce_exercise_evidence: bool = True,
    repository_root: Path = ROOT,
) -> list[str]:
    if not contract_path.is_file():
        return [f"{contract_path}: incident-response contract does not exist"]
    if not monitoring_path.is_file():
        return [f"{monitoring_path}: monitoring contract does not exist"]

    try:
        contract = _load_object(contract_path)
    except DuplicateJsonKeyError:
        return [f"{contract_path}: duplicate JSON object keys are forbidden"]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return [f"{contract_path}: incident-response contract must be a JSON object"]
    try:
        monitoring = _load_object(monitoring_path)
    except DuplicateJsonKeyError:
        return [f"{monitoring_path}: duplicate JSON object keys are forbidden"]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return [f"{monitoring_path}: monitoring contract must be a JSON object"]
    issues: list[str] = []
    issues.extend(validate_observability_contract(monitoring_path))

    if set(contract) != CONTRACT_FIELDS:
        issues.append("contract fields do not match the governed schema")
    if contract.get("contract_id") != "lotus-risk:incident-response:v1":
        issues.append("contract_id must be lotus-risk:incident-response:v1")
    if contract.get("contract_version") != "1.0.0":
        issues.append("contract_version must be 1.0.0")
    if contract.get("service") != "lotus-risk" or contract.get("owner_repository") != "lotus-risk":
        issues.append("service and owner_repository must remain lotus-risk")
    if contract.get("status") not in GOVERNED_CONTRACT_STATUSES:
        issues.append("status is not governed")
    if contract.get("production_acceptance") is not False:
        issues.append("repository contract must not claim production acceptance")
    if contract.get("incident_runbook") != CANONICAL_INCIDENT_RUNBOOK:
        issues.append("incident_runbook must remain docs/runbooks/incident-response.md")
    issues.extend(
        _validate_incident_runbook(
            contract.get("incident_runbook"),
            contract_status=contract.get("status"),
            production_acceptance=contract.get("production_acceptance"),
            repository_root=repository_root,
        )
    )
    issues.extend(_validate_lifecycle_pointer_documents(repository_root))

    severity_model = contract.get("severity_model")
    if not isinstance(severity_model, dict) or set(severity_model) != ALLOWED_SEVERITIES:
        issues.append("severity_model must define exactly SEV1 and SEV2")
    else:
        for severity, definition in severity_model.items():
            if not isinstance(definition, dict) or set(definition) != {
                "acknowledgement_target",
                "meaning",
            }:
                issues.append(f"{severity}: severity fields do not match the governed schema")
            elif not _is_nonblank_string(definition.get("meaning")):
                issues.append(f"{severity}: severity meaning is required")
            elif definition.get("meaning") != GOVERNED_SEVERITY_MEANINGS[severity]:
                issues.append(
                    f"{severity}: severity meaning does not match the governed definition"
                )
            elif definition.get("acknowledgement_target") != "deployment_policy_required":
                issues.append(f"{severity}: acknowledgement target must remain deployment-owned")

    escalation = contract.get("escalation_model")
    if not isinstance(escalation, dict):
        issues.append("escalation_model must be an object")
    else:
        if set(escalation) != ESCALATION_FIELDS:
            issues.append("escalation_model fields do not match the governed schema")
        if escalation.get("contact_source") != "deployment_controlled_contact_directory":
            issues.append("contacts must resolve from the deployment-controlled directory")
        if escalation.get("assignment_status") != "deployment_assignment_required":
            issues.append("contact assignments must remain an explicit deployment requirement")
        roles = escalation.get("roles")
        if not _matches_unique_string_set(roles, ALLOWED_ROLES):
            issues.append("escalation roles do not match the governed role set")

    evidence_fields = contract.get("source_safe_evidence_fields")
    if not _matches_unique_string_set(evidence_fields, ALLOWED_EVIDENCE_FIELDS):
        issues.append("source_safe_evidence_fields must match the governed allowlist")

    monitoring_alerts = monitoring.get("alerts")
    if not isinstance(monitoring_alerts, list):
        return issues + ["monitoring alerts must be a list"]
    monitoring_by_id: dict[str, dict[str, Any]] = {}
    monitoring_alert_ids: list[str] = []
    for alert in monitoring_alerts:
        if not isinstance(alert, dict):
            issues.append("monitoring alert entries must be objects")
            continue
        alert_id = alert.get("alert_id")
        if isinstance(alert_id, str) and alert_id.strip():
            monitoring_alert_ids.append(alert_id)
            monitoring_by_id[alert_id] = alert
        else:
            issues.append("monitoring alert entries require a nonblank string alert_id")
    if len(monitoring_alert_ids) != len(set(monitoring_alert_ids)):
        issues.append("monitoring contract contains duplicate alert_id values")
    if set(monitoring_alert_ids) != GOVERNED_ALERT_IDS:
        missing = sorted(GOVERNED_ALERT_IDS - set(monitoring_alert_ids))
        extra = sorted(set(monitoring_alert_ids) - GOVERNED_ALERT_IDS)
        issues.append(
            f"governed monitoring alert inventory mismatch: missing={missing}, extra={extra}"
        )

    responses = contract.get("alert_responses")
    if not isinstance(responses, list):
        return issues + ["alert_responses must be a list"]
    response_ids: list[str] = []
    for response in responses:
        if not isinstance(response, dict):
            continue
        alert_id = response.get("alert_id")
        if isinstance(alert_id, str) and alert_id.strip():
            response_ids.append(alert_id)
        else:
            issues.append("alert response entries require a nonblank string alert_id")
    if len(response_ids) != len(set(response_ids)):
        issues.append("alert_responses contains duplicate alert_id values")
    if set(response_ids) != set(monitoring_by_id):
        missing = sorted(set(monitoring_by_id) - set(response_ids))
        extra = sorted(set(response_ids) - set(monitoring_by_id))
        issues.append(f"alert response coverage mismatch: missing={missing}, extra={extra}")
    response_profiles_digest = _response_profiles_sha256(contract)
    if response_profiles_digest != GOVERNED_RESPONSE_PROFILES_SHA256:
        issues.append("governed per-alert response profiles do not match")

    for response in responses:
        if not isinstance(response, dict):
            issues.append("alert response entries must be objects")
            continue
        alert_id = response.get("alert_id")
        if not isinstance(alert_id, str) or not alert_id.strip():
            continue
        monitoring_alert = monitoring_by_id.get(alert_id)
        if monitoring_alert is None:
            continue
        if not _is_nonblank_string(response.get("incident_class")):
            issues.append(f"{alert_id}: incident_class is required")
        monitoring_severity = response.get("monitoring_severity")
        if monitoring_severity not in ALLOWED_MONITORING_SEVERITIES:
            issues.append(f"{alert_id}: monitoring_severity is not governed")
        if monitoring_severity != monitoring_alert.get("severity"):
            issues.append(f"{alert_id}: monitoring severity does not match monitoring contract")
        incident_severity = response.get("incident_severity")
        if incident_severity not in ALLOWED_SEVERITIES:
            issues.append(f"{alert_id}: incident_severity is not governed")
        if (monitoring_severity, incident_severity) != GOVERNED_ALERT_SEVERITIES.get(alert_id):
            issues.append(f"{alert_id}: governed alert severities do not match")
        if monitoring_severity == "critical" and incident_severity != "SEV1":
            issues.append(f"{alert_id}: critical monitoring alerts must map to SEV1")
        if monitoring_severity == "warning" and incident_severity != "SEV2":
            issues.append(f"{alert_id}: warning monitoring alerts must map to SEV2")
        if response.get("runbook") != monitoring_alert.get("runbook"):
            issues.append(f"{alert_id}: runbook does not match monitoring contract")
        runbook = response.get("runbook")
        if not isinstance(runbook, str) or not _markdown_anchor_exists(
            runbook, repository_root=repository_root
        ):
            issues.append(f"{alert_id}: runbook anchor does not exist")
        for field in ("initial_containment", "recovery_reconciliation"):
            if not _non_empty_strings(response.get(field)):
                issues.append(f"{alert_id}: {field} must contain bounded actions")
        roles = response.get("escalation_roles")
        if (
            not isinstance(roles, list)
            or not _non_empty_strings(roles)
            or len(roles) != len(set(roles))
            or not set(roles) <= ALLOWED_ROLES
        ):
            issues.append(f"{alert_id}: escalation_roles are missing or unknown")
        elif incident_severity == "SEV1" and "incident_commander" not in roles:
            issues.append(f"{alert_id}: SEV1 escalation requires incident_commander")
        elif incident_severity == "SEV2" and "service_support_owner" not in roles:
            issues.append(f"{alert_id}: SEV2 escalation requires service_support_owner")
        preserved = response.get("evidence_preservation")
        if not isinstance(preserved, list) or not preserved:
            issues.append(f"{alert_id}: evidence_preservation must be non-empty")
        elif not set(preserved) <= ALLOWED_EVIDENCE_FIELDS:
            issues.append(f"{alert_id}: evidence_preservation contains unsafe or unknown fields")

    credential_response = contract.get("credential_response")
    if not isinstance(credential_response, dict):
        issues.append("credential_response must be an object")
    else:
        if set(credential_response) != CREDENTIAL_RESPONSE_FIELDS:
            issues.append("credential_response fields do not match the governed schema")
        if credential_response.get("owner") != "deployment_authority":
            issues.append("credential response must remain deployment-authority owned")
        if credential_response.get("repository_secret_material_permitted") is not False:
            issues.append("repository secret material must remain forbidden")
        actions = credential_response.get("actions")
        if not isinstance(actions, list) or not _non_empty_strings(actions):
            issues.append("credential response actions are required")
        elif set(actions) != REQUIRED_CREDENTIAL_ACTIONS or len(actions) != len(
            REQUIRED_CREDENTIAL_ACTIONS
        ):
            issues.append("credential response actions must match the governed action set")

    exercise = contract.get("exercise_evidence")
    if not isinstance(exercise, dict):
        issues.append("exercise_evidence must be an object")
    else:
        if set(exercise) != EXERCISE_FIELDS:
            issues.append("exercise_evidence fields do not match the governed schema")
        raw_status = exercise.get("status")
        status = raw_status if isinstance(raw_status, str) else None
        references = exercise.get("evidence_references")
        if status not in ALLOWED_EXERCISE_STATUSES:
            issues.append("exercise status is not governed")
        expected_contract_status = None
        if status == "not_exercised":
            expected_contract_status = "prepared_not_exercised"
        elif status == "planned":
            expected_contract_status = "exercise_planned"
        elif status == "exercised":
            expected_contract_status = "exercised"
        if (
            expected_contract_status is not None
            and contract.get("status") != expected_contract_status
        ):
            issues.append("contract status does not match exercise status")
        if enforce_exercise_evidence:
            issues.extend(
                _validate_exercise_evidence_references(
                    status,
                    references,
                    expected_contract_revision_sha256=_incident_contract_revision_sha256(
                        contract,
                        monitoring_path=monitoring_path,
                        repository_root=repository_root,
                    ),
                    expected_alert_roles={
                        str(response.get("alert_id")): set(response.get("escalation_roles", []))
                        for response in responses
                        if isinstance(response, dict)
                        and isinstance(response.get("escalation_roles"), list)
                    },
                    expected_evidence_fields={
                        str(response.get("alert_id")): set(
                            response.get("evidence_preservation", [])
                        )
                        for response in responses
                        if isinstance(response, dict)
                        and isinstance(response.get("evidence_preservation"), list)
                    },
                    expected_response_profiles_sha256=response_profiles_digest,
                    repository_root=repository_root,
                )
            )
        if exercise.get("production_claim") is not False:
            issues.append("exercise evidence must not claim production readiness")

    action_model = contract.get("corrective_action_model")
    if not isinstance(action_model, dict):
        issues.append("corrective_action_model must be an object")
    else:
        if set(action_model) != CORRECTIVE_ACTION_FIELDS:
            issues.append("corrective_action_model fields do not match the governed schema")
        if not _matches_unique_string_set(
            action_model.get("required_fields"), REQUIRED_ACTION_FIELDS
        ):
            issues.append("corrective action required fields do not match the governed model")
        if not _matches_unique_string_set(
            action_model.get("allowed_statuses"), ALLOWED_ACTION_STATUSES
        ):
            issues.append("corrective action statuses do not match the governed model")

    deployment_blockers = contract.get("deployment_blockers")
    if not isinstance(deployment_blockers, list) or not _non_empty_strings(deployment_blockers):
        issues.append("deployment_blockers must state unresolved production evidence")
    else:
        expected_blockers = set(BASE_DEPLOYMENT_BLOCKERS)
        if contract.get("status") != "exercised":
            expected_blockers.add(EXERCISE_EVIDENCE_BLOCKER)
        actual_blockers = set(deployment_blockers)
        if actual_blockers != expected_blockers:
            issues.append(
                "deployment blockers do not match the governed lifecycle set: "
                f"missing={sorted(expected_blockers - actual_blockers)}, "
                f"extra={sorted(actual_blockers - expected_blockers)}"
            )

    return issues


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Risk incident-response contract.")
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--monitoring-contract", type=Path, default=MONITORING_PATH)
    parser.add_argument(
        "--prepare-exercise-revision",
        action="store_true",
        help="emit candidate revisions before enforcing lifecycle evidence",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        issues = validate_incident_response_contract(
            args.contract,
            args.monitoring_contract,
            enforce_exercise_evidence=not args.prepare_exercise_revision,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(exc)
        return 1
    if issues:
        for issue in issues:
            print(issue)
        return 1
    validation_kind = "exercise-revision inputs" if args.prepare_exercise_revision else "contract"
    print(f"Validated incident-response {validation_kind} at {args.contract}")
    contract = _load_object(args.contract)
    print(
        "Contract revision SHA-256: "
        f"{_incident_contract_revision_sha256(contract, monitoring_path=args.monitoring_contract)}"
    )
    print(f"Response profiles SHA-256: {_response_profiles_sha256(contract)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
