from __future__ import annotations

import datetime as dt
import os

from sqlalchemy.exc import SQLAlchemyError

from app.scenario_jobs.contracts import (
    RegimeScenarioPackJobRequest,
    ScenarioEvaluationJobAccepted,
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
    return ScenarioEvaluationJobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        request_fingerprint=record.request_fingerprint,
        scenario_pack_revision=record.scenario_pack_revision,
        expires_at=record.expires_at,
        submitted_at=record.submitted_at,
    )


__all__ = [
    "ScenarioJobAdmissionConflict",
    "ScenarioJobStoreUnavailable",
    "configured_scenario_job_store",
    "scenario_job_status_response",
    "submit_scenario_job",
]
