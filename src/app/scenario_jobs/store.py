from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ScenarioEvaluationJobModel
from app.scenario_jobs.contracts import ScenarioEvaluationJobStatus


class ScenarioJobIdempotencyConflict(ValueError):
    """A tenant reused its idempotency key with different immutable input."""


@dataclass(frozen=True, slots=True)
class ScenarioEvaluationJobRecord:
    job_id: str
    tenant_id: str
    idempotency_key: str
    request_fingerprint: str
    scenario_pack_id: str
    scenario_pack_revision: str
    immutable_request_json: str
    status: ScenarioEvaluationJobStatus
    actor_id: str | None
    correlation_id: str | None
    submitted_at: dt.datetime
    expires_at: dt.datetime


class SqlAlchemyScenarioJobStore:
    """Relational job admission store; SQLite is supported only for isolated tests."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)

    def close(self) -> None:
        self._engine.dispose()

    def is_schema_ready(self) -> bool:
        """Refuse admission until the exact store is reachable and its job table exists."""
        try:
            return inspect(self._engine).has_table(ScenarioEvaluationJobModel.__tablename__)
        except SQLAlchemyError:
            return False

    def submit(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        scenario_pack_id: str,
        scenario_pack_revision: str,
        immutable_request: dict[str, object],
        actor_id: str | None,
        correlation_id: str | None,
        submitted_at: dt.datetime,
        expires_at: dt.datetime,
    ) -> tuple[ScenarioEvaluationJobRecord, bool]:
        """Commit immutable input and initial state together, or return the keyed replay."""
        serialized_input = json.dumps(immutable_request, sort_keys=True, separators=(",", ":"))
        candidate = ScenarioEvaluationJobModel(
            job_id=str(uuid4()),
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            scenario_pack_id=scenario_pack_id,
            scenario_pack_revision=scenario_pack_revision,
            immutable_request_json=serialized_input,
            status=ScenarioEvaluationJobStatus.QUEUED.value,
            actor_id=actor_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            expires_at=expires_at,
        )
        with self._session_factory() as session:
            try:
                session.add(candidate)
                session.commit()
                session.refresh(candidate)
                return _record(candidate), True
            except IntegrityError:
                session.rollback()
                existing = _get_by_key(
                    session,
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    lock=True,
                )
                if existing is None:
                    # A concurrent transaction has not become visible yet. The caller must retry;
                    # do not fabricate a different job identity after a uniqueness conflict.
                    raise RuntimeError("Scenario job idempotency outcome is not yet visible")
                if existing.request_fingerprint != request_fingerprint:
                    raise ScenarioJobIdempotencyConflict(
                        "Idempotency-Key was previously used with different scenario job input"
                    )
                return _record(existing), False

    def get_for_tenant(self, *, tenant_id: str, job_id: str) -> ScenarioEvaluationJobRecord | None:
        with self._session_factory() as session:
            model = session.scalar(
                select(ScenarioEvaluationJobModel).where(
                    ScenarioEvaluationJobModel.tenant_id == tenant_id,
                    ScenarioEvaluationJobModel.job_id == job_id,
                )
            )
            return _record(model) if model is not None else None


def _get_by_key(
    session: Session,
    *,
    tenant_id: str,
    idempotency_key: str,
    lock: bool,
) -> ScenarioEvaluationJobModel | None:
    statement = select(ScenarioEvaluationJobModel).where(
        ScenarioEvaluationJobModel.tenant_id == tenant_id,
        ScenarioEvaluationJobModel.idempotency_key == idempotency_key,
    )
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _record(model: ScenarioEvaluationJobModel) -> ScenarioEvaluationJobRecord:
    return ScenarioEvaluationJobRecord(
        job_id=model.job_id,
        tenant_id=model.tenant_id,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint,
        scenario_pack_id=model.scenario_pack_id,
        scenario_pack_revision=model.scenario_pack_revision,
        immutable_request_json=model.immutable_request_json,
        status=ScenarioEvaluationJobStatus(model.status),
        actor_id=model.actor_id,
        correlation_id=model.correlation_id,
        submitted_at=model.submitted_at,
        expires_at=model.expires_at,
    )


__all__ = [
    "ScenarioEvaluationJobRecord",
    "ScenarioJobIdempotencyConflict",
    "SqlAlchemyScenarioJobStore",
]
