"""Fail-closed structural readiness checks for durable scenario-job persistence."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import ScenarioEvaluationJobContributionModel, ScenarioEvaluationJobModel

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
        "result_json",
        "completed_at",
        "submitted_at",
        "expires_at",
    }
)
_REQUIRED_PRIMARY_KEY = frozenset({"job_id"})
_REQUIRED_UNIQUE_KEYS = frozenset({frozenset({"tenant_id", "idempotency_key"})})
_REQUIRED_CONTRIBUTION_COLUMNS = frozenset(
    {
        "job_id",
        "scenario_id",
        "ordinal",
        "security_id",
        "display_name",
        "bucket",
        "weight",
        "shock_pct",
        "contribution_loss_pct",
    }
)
_REQUIRED_CONTRIBUTION_PRIMARY_KEY = frozenset({"job_id", "scenario_id", "ordinal"})


def is_scenario_job_schema_ready(engine: Engine) -> bool:
    """Require every mapped durable-job invariant without equating readiness to one revision label."""
    try:
        inspector = inspect(engine)
        table_name = ScenarioEvaluationJobModel.__tablename__
        return (
            inspector.has_table(table_name)
            and _has_required_job_columns(inspector, table_name)
            and _has_required_primary_key(inspector, table_name)
            and _has_required_unique_keys(inspector, table_name)
            and _has_required_contribution_table(inspector)
        )
    except SQLAlchemyError:
        return False


def _has_required_job_columns(inspector: Inspector, table_name: str) -> bool:
    available_columns = {column["name"] for column in inspector.get_columns(table_name)}
    return _REQUIRED_JOB_COLUMNS.issubset(available_columns)


def _has_required_primary_key(inspector: Inspector, table_name: str) -> bool:
    return _constraint_columns(inspector.get_pk_constraint(table_name)) == _REQUIRED_PRIMARY_KEY


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


def _has_required_contribution_table(inspector: Inspector) -> bool:
    table_name = ScenarioEvaluationJobContributionModel.__tablename__
    if not inspector.has_table(table_name):
        return False
    available_columns = {column["name"] for column in inspector.get_columns(table_name)}
    return _REQUIRED_CONTRIBUTION_COLUMNS.issubset(available_columns) and (
        _constraint_columns(inspector.get_pk_constraint(table_name))
        == _REQUIRED_CONTRIBUTION_PRIMARY_KEY
    )


def _constraint_columns(constraint: Mapping[str, object]) -> frozenset[str]:
    column_names = constraint.get("column_names") or constraint.get("constrained_columns") or ()
    if not isinstance(column_names, (list, tuple)):
        return frozenset()
    return frozenset(column for column in column_names if isinstance(column, str))


__all__ = ["is_scenario_job_schema_ready"]
