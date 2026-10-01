from __future__ import annotations

import datetime as dt
import json
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode

from sqlalchemy.exc import SQLAlchemyError

from app.contracts.scenario_response_outputs import RegimeScenarioPackResponse
from app.scenario_jobs.contracts import (
    RegimeScenarioPackJobRequest,
    ScenarioEvaluationJobAccepted,
    ScenarioEvaluationJobContribution,
    ScenarioEvaluationJobContributionPage,
    ScenarioEvaluationJobStatusResponse,
)
from app.scenario_jobs.identity import canonical_request_fingerprint, scenario_pack_revision
from app.scenario_jobs.store import ScenarioJobIdempotencyConflict, SqlAlchemyScenarioJobStore
from app.services.scenario_pack_catalog import SCENARIO_PACKS


class ScenarioJobStoreUnavailable(RuntimeError):
    """Job admission is disabled until a configured, migrated relational store is available."""


def configured_scenario_job_store() -> SqlAlchemyScenarioJobStore:
    database_url = os.getenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", "").strip()
    if not database_url:
        raise ScenarioJobStoreUnavailable(
            "Scenario job admission is unavailable because LOTUS_RISK_SCENARIO_JOB_DATABASE_URL is not configured"
        )
    try:
        store = SqlAlchemyScenarioJobStore(database_url)
    except SQLAlchemyError as exc:
        raise ScenarioJobStoreUnavailable("Scenario job store configuration is invalid") from exc
    if store.is_schema_ready():
        return store
    store.close()
    raise ScenarioJobStoreUnavailable(
        "Scenario job admission is unavailable because the configured store is not migrated or reachable"
    )


class ScenarioJobAdmissionConflict(ValueError):
    """A keyed replay has a different immutable request digest."""


def retention_hours() -> int:
    raw_value = os.getenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "").strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ScenarioJobStoreUnavailable(
            "Scenario job admission requires a positive LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS"
        ) from exc
    if value <= 0:
        raise ScenarioJobStoreUnavailable(
            "Scenario job admission requires a positive LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS"
        )
    return value


def submit_scenario_job(
    *,
    store: SqlAlchemyScenarioJobStore,
    tenant_id: str,
    idempotency_key: str,
    request: RegimeScenarioPackJobRequest,
    actor_id: str | None,
    correlation_id: str | None,
    now: dt.datetime | None = None,
) -> ScenarioEvaluationJobAccepted:
    if request.scenario_pack_id not in SCENARIO_PACKS:
        raise ValueError(f"Unsupported scenario_pack_id: {request.scenario_pack_id}")
    submitted_at = now or dt.datetime.now(tz=dt.UTC)
    expires_at = submitted_at + dt.timedelta(hours=retention_hours())
    try:
        record, _created = store.submit(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=canonical_request_fingerprint(request),
            scenario_pack_id=request.scenario_pack_id,
            scenario_pack_revision=scenario_pack_revision(request.scenario_pack_id),
            immutable_request=request.model_dump(mode="json"),
            actor_id=actor_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            expires_at=expires_at,
        )
    except ScenarioJobIdempotencyConflict as exc:
        raise ScenarioJobAdmissionConflict(str(exc)) from exc
    return ScenarioEvaluationJobAccepted(
        job_id=record.job_id,
        status=record.status,
        request_fingerprint=record.request_fingerprint,
        scenario_pack_revision=record.scenario_pack_revision,
        expires_at=record.expires_at,
    )


def scenario_job_status_response(
    *, store: SqlAlchemyScenarioJobStore, tenant_id: str, job_id: str
) -> ScenarioEvaluationJobStatusResponse | None:
    record = store.get_for_tenant(tenant_id=tenant_id, job_id=job_id)
    if record is None:
        return None
    result = (
        RegimeScenarioPackResponse.model_validate(json.loads(record.result_json))
        if record.result_json is not None
        else None
    )
    return ScenarioEvaluationJobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        request_fingerprint=record.request_fingerprint,
        scenario_pack_revision=record.scenario_pack_revision,
        expires_at=record.expires_at,
        submitted_at=record.submitted_at,
        failure_code=record.failure_code,
        result=result,
    )


def scenario_job_contribution_page(
    *,
    store: SqlAlchemyScenarioJobStore,
    tenant_id: str,
    job_id: str,
    cursor: str | None,
    limit: int,
) -> ScenarioEvaluationJobContributionPage | None:
    after = _decode_contribution_cursor(cursor) if cursor is not None else None
    rows = store.contribution_page(tenant_id=tenant_id, job_id=job_id, after=after, limit=limit)
    if rows is None:
        return None
    page_rows = rows[:limit]
    next_cursor = (
        _encode_contribution_cursor(page_rows[-1].scenario_id, page_rows[-1].ordinal)
        if len(rows) > limit and page_rows
        else None
    )
    return ScenarioEvaluationJobContributionPage(
        job_id=job_id,
        contributions=[
            ScenarioEvaluationJobContribution(
                scenario_id=row.scenario_id,
                security_id=row.security_id,
                display_name=row.display_name,
                bucket=row.bucket,
                weight=row.weight,
                shock_pct=row.shock_pct,
                contribution_loss_pct=row.contribution_loss_pct,
            )
            for row in page_rows
        ],
        next_cursor=next_cursor,
    )


def _encode_contribution_cursor(scenario_id: str, ordinal: int) -> str:
    payload = json.dumps([scenario_id, ordinal], separators=(",", ":")).encode("utf-8")
    return urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_contribution_cursor(cursor: str) -> tuple[str, int]:
    padding = "=" * (-len(cursor) % 4)
    try:
        raw = json.loads(urlsafe_b64decode(cursor + padding).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("scenario job contribution cursor is invalid") from exc
    if (
        not isinstance(raw, list)
        or len(raw) != 2
        or not isinstance(raw[0], str)
        or not raw[0]
        or not isinstance(raw[1], int)
        or raw[1] < 0
    ):
        raise ValueError("scenario job contribution cursor is invalid")
    return raw[0], raw[1]


__all__ = [
    "ScenarioJobAdmissionConflict",
    "ScenarioJobStoreUnavailable",
    "configured_scenario_job_store",
    "scenario_job_contribution_page",
    "scenario_job_status_response",
    "submit_scenario_job",
]
