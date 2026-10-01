from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import and_, create_engine, delete, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ScenarioEvaluationJobContributionModel, ScenarioEvaluationJobModel
from app.scenario_jobs.contracts import ScenarioEvaluationJobStatus
from app.scenario_jobs.schema import is_scenario_job_schema_ready


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
    claim_token: str | None
    lease_expires_at: dt.datetime | None
    attempt_count: int
    failure_code: str | None
    failure_detail: str | None
    result_json: str | None
    completed_at: dt.datetime | None
    submitted_at: dt.datetime
    expires_at: dt.datetime


@dataclass(frozen=True, slots=True)
class ScenarioEvaluationJobContributionRecord:
    job_id: str
    scenario_id: str
    ordinal: int
    security_id: str
    display_name: str | None
    bucket: str
    weight: float
    shock_pct: float
    contribution_loss_pct: float


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
        return is_scenario_job_schema_ready(self._engine)

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

    def complete_claim(
        self,
        *,
        job_id: str,
        claim_token: str,
        aggregate_result: dict[str, object],
        contributions: list[ScenarioEvaluationJobContributionRecord],
        completed_at: dt.datetime,
    ) -> bool:
        """Atomically publish one complete success only for the current claim token.

        The aggregate document and every contribution row share the durable terminal transaction.
        A stale claimant cannot publish either a partial page set or a conflicting terminal result.
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
            if any(row.job_id != job_id for row in contributions):
                raise ValueError("scenario-job contribution does not belong to the claimed job")
            session.add_all(
                [
                    ScenarioEvaluationJobContributionModel(
                        job_id=row.job_id,
                        scenario_id=row.scenario_id,
                        ordinal=row.ordinal,
                        security_id=row.security_id,
                        display_name=row.display_name,
                        bucket=row.bucket,
                        weight=row.weight,
                        shock_pct=row.shock_pct,
                        contribution_loss_pct=row.contribution_loss_pct,
                    )
                    for row in contributions
                ]
            )
            model.status = ScenarioEvaluationJobStatus.SUCCEEDED.value
            model.result_json = json.dumps(aggregate_result, sort_keys=True, separators=(",", ":"))
            model.completed_at = completed_at
            model.lease_expires_at = completed_at
            model.failure_code = None
            model.failure_detail = None
            session.flush()
            return True

    def contribution_page(
        self,
        *,
        tenant_id: str,
        job_id: str,
        after: tuple[str, int] | None,
        limit: int,
    ) -> list[ScenarioEvaluationJobContributionRecord] | None:
        """Read at most ``limit + 1`` durable rows, only from a completed tenant-owned job."""
        with self._session_factory() as session:
            job = session.scalar(
                select(ScenarioEvaluationJobModel).where(
                    ScenarioEvaluationJobModel.tenant_id == tenant_id,
                    ScenarioEvaluationJobModel.job_id == job_id,
                )
            )
            if job is None or job.status != ScenarioEvaluationJobStatus.SUCCEEDED.value:
                return None
            statement = select(ScenarioEvaluationJobContributionModel).where(
                ScenarioEvaluationJobContributionModel.job_id == job_id
            )
            if after is not None:
                scenario_id, ordinal = after
                statement = statement.where(
                    or_(
                        ScenarioEvaluationJobContributionModel.scenario_id > scenario_id,
                        and_(
                            ScenarioEvaluationJobContributionModel.scenario_id == scenario_id,
                            ScenarioEvaluationJobContributionModel.ordinal > ordinal,
                        ),
                    )
                )
            models = session.scalars(
                statement.order_by(
                    ScenarioEvaluationJobContributionModel.scenario_id,
                    ScenarioEvaluationJobContributionModel.ordinal,
                ).limit(limit + 1)
            ).all()
            return [_contribution_record(model) for model in models]

    def delete_expired(self, *, now: dt.datetime, limit: int) -> int:
        """Delete at most ``limit`` expired jobs and their contribution evidence.

        The bounded lock-backed selection lets concurrent cleanup workers progress without
        selecting each other's rows. Expiry is the only eligibility condition: a non-expired
        queued, running, failed, or successful record remains durable evidence.
        """
        if limit <= 0:
            raise ValueError("scenario job cleanup limit must be positive")
        with self._session_factory.begin() as session:
            models = session.scalars(
                select(ScenarioEvaluationJobModel)
                .where(ScenarioEvaluationJobModel.expires_at <= now)
                .order_by(ScenarioEvaluationJobModel.expires_at, ScenarioEvaluationJobModel.job_id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
            job_ids = [model.job_id for model in models]
            if not job_ids:
                return 0
            session.execute(
                delete(ScenarioEvaluationJobContributionModel).where(
                    ScenarioEvaluationJobContributionModel.job_id.in_(job_ids)
                )
            )
            session.execute(
                delete(ScenarioEvaluationJobModel).where(
                    ScenarioEvaluationJobModel.job_id.in_(job_ids)
                )
            )
            return len(job_ids)


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
        result_json=model.result_json,
        completed_at=model.completed_at,
        submitted_at=model.submitted_at,
        expires_at=model.expires_at,
    )


def _contribution_record(
    model: ScenarioEvaluationJobContributionModel,
) -> ScenarioEvaluationJobContributionRecord:
    return ScenarioEvaluationJobContributionRecord(
        job_id=model.job_id,
        scenario_id=model.scenario_id,
        ordinal=model.ordinal,
        security_id=model.security_id,
        display_name=model.display_name,
        bucket=model.bucket,
        weight=model.weight,
        shock_pct=model.shock_pct,
        contribution_loss_pct=model.contribution_loss_pct,
    )


__all__ = [
    "ScenarioEvaluationJobContributionRecord",
    "ScenarioEvaluationJobRecord",
    "ScenarioJobIdempotencyConflict",
    "SqlAlchemyScenarioJobStore",
]
