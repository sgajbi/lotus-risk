from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import and_, create_engine, inspect, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ScenarioEvaluationJobModel
from app.scenario_jobs.contracts import ScenarioEvaluationJobStatus


class ScenarioJobIdempotencyConflict(ValueError):
    """A tenant reused its idempotency key with different immutable input."""


_REQUIRED_JOB_COLUMNS = frozenset(
    {
        "job_id",
        "tenant_id",
        "idempotency_key",
        "request_fingerprint",
        "scenario_pack_id",
        "scenario_pack_revision",
        "immutable_request_json",
        "status",
        "actor_id",
        "correlation_id",
        "claim_token",
        "lease_expires_at",
        "attempt_count",
        "failure_code",
        "failure_detail",
        "submitted_at",
        "expires_at",
    }
)
_REQUIRED_PRIMARY_KEY = frozenset({"job_id"})
_REQUIRED_UNIQUE_KEYS = frozenset({frozenset({"tenant_id", "idempotency_key"})})


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
    claim_token: str | None
    lease_expires_at: dt.datetime | None
    attempt_count: int
    failure_code: str | None
    failure_detail: str | None
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
        """Refuse admission until the store can uphold the current durable-job contract.

        Request handling never upgrades a database.  Instead it requires every mapped column plus
        the primary and tenant/idempotency uniqueness constraints that make replay safe.  This is a
        minimum structural contract, not an Alembic revision equality check: a future migration may
        add compatible columns or indexes without making this application unavailable.
        """
        try:
            inspector = inspect(self._engine)
            table_name = ScenarioEvaluationJobModel.__tablename__
            if not inspector.has_table(table_name):
                return False
            return (
                _has_required_job_columns(inspector, table_name)
                and _has_required_primary_key(inspector, table_name)
                and _has_required_unique_keys(inspector, table_name)
            )
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

    def claim_next(
        self, *, now: dt.datetime, lease_expires_at: dt.datetime
    ) -> ScenarioEvaluationJobRecord | None:
        """Atomically claim one queued job or reclaim one expired lease.

        PostgreSQL evaluates the row lock with ``SKIP LOCKED`` so concurrent workers do not wait
        behind the same candidate. SQLite remains an isolated test-only implementation; its
        transaction still establishes a single durable state transition before the returned claim.
        """
        if lease_expires_at <= now:
            raise ValueError("claim lease expiry must be after the claim timestamp")
        candidate_filter = or_(
            ScenarioEvaluationJobModel.status == ScenarioEvaluationJobStatus.QUEUED.value,
            and_(
                ScenarioEvaluationJobModel.status == ScenarioEvaluationJobStatus.RUNNING.value,
                ScenarioEvaluationJobModel.lease_expires_at.is_not(None),
                ScenarioEvaluationJobModel.lease_expires_at <= now,
            ),
        )
        with self._session_factory.begin() as session:
            statement = (
                select(ScenarioEvaluationJobModel)
                .where(
                    candidate_filter,
                    ScenarioEvaluationJobModel.expires_at > now,
                )
                .order_by(
                    ScenarioEvaluationJobModel.submitted_at, ScenarioEvaluationJobModel.job_id
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            model = session.scalar(statement)
            if model is None:
                return None
            model.status = ScenarioEvaluationJobStatus.RUNNING.value
            model.claim_token = str(uuid4())
            model.lease_expires_at = lease_expires_at
            model.attempt_count += 1
            model.failure_code = None
            model.failure_detail = None
            session.flush()
            return _record(model)

    def fail_claim(
        self,
        *,
        job_id: str,
        claim_token: str,
        failure_code: str,
        failure_detail: str,
        failed_at: dt.datetime,
    ) -> bool:
        """Fence terminal failure on the currently durable claim token.

        A stale claimant is not allowed to overwrite a reclaimed claim or a terminal result. The
        operation is deliberately idempotent at the caller boundary: ``False`` means no state was
        changed and the caller must not report a terminal transition.
        """
        with self._session_factory.begin() as session:
            model = session.scalar(
                select(ScenarioEvaluationJobModel)
                .where(ScenarioEvaluationJobModel.job_id == job_id)
                .with_for_update()
            )
            if (
                model is None
                or model.status != ScenarioEvaluationJobStatus.RUNNING.value
                or model.claim_token != claim_token
            ):
                return False
            model.status = ScenarioEvaluationJobStatus.FAILED.value
            model.lease_expires_at = failed_at
            model.failure_code = failure_code
            model.failure_detail = failure_detail
            session.flush()
            return True


def _has_required_job_columns(inspector: Inspector, table_name: str) -> bool:
    available_columns = {column["name"] for column in inspector.get_columns(table_name)}
    return _REQUIRED_JOB_COLUMNS.issubset(available_columns)


def _has_required_primary_key(inspector: Inspector, table_name: str) -> bool:
    primary_key = _constraint_columns(inspector.get_pk_constraint(table_name))
    return primary_key == _REQUIRED_PRIMARY_KEY


def _has_required_unique_keys(inspector: Inspector, table_name: str) -> bool:
    unique_keys = {
        _constraint_columns(constraint)
        for constraint in inspector.get_unique_constraints(table_name)
    }
    unique_keys.update(
        _constraint_columns(index)
        for index in inspector.get_indexes(table_name)
        if index.get("unique")
    )
    return _REQUIRED_UNIQUE_KEYS.issubset(unique_keys)


def _constraint_columns(constraint: Mapping[str, object]) -> frozenset[str]:
    column_names = constraint.get("column_names") or constraint.get("constrained_columns") or ()
    if not isinstance(column_names, (list, tuple)):
        return frozenset()
    return frozenset(column for column in column_names if isinstance(column, str))


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
        claim_token=model.claim_token,
        lease_expires_at=model.lease_expires_at,
        attempt_count=model.attempt_count,
        failure_code=model.failure_code,
        failure_detail=model.failure_detail,
        submitted_at=model.submitted_at,
        expires_at=model.expires_at,
    )


__all__ = [
    "ScenarioEvaluationJobRecord",
    "ScenarioJobIdempotencyConflict",
    "SqlAlchemyScenarioJobStore",
]
