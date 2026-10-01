from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.scenario_jobs import service
from app.scenario_jobs import service as scenario_job_service
from app.scenario_jobs.contracts import (
    RegimeScenarioPackJobRequest,
    ScenarioEvaluationJobStatus,
)
from app.scenario_jobs.identity import (
    canonical_request_fingerprint,
    normalize_idempotency_key,
    scenario_pack_revision,
)
from app.scenario_jobs.service import (
    ScenarioJobAdmissionConflict,
    ScenarioJobStoreUnavailable,
    configured_scenario_job_store,
    retention_hours,
    scenario_job_status_response,
    submit_scenario_job,
)
from app.scenario_jobs.store import (
    ScenarioEvaluationJobRecord,
    ScenarioJobIdempotencyConflict,
    SqlAlchemyScenarioJobStore,
)


def _request(*, components: list[dict[str, object]] | None = None) -> RegimeScenarioPackJobRequest:
    return RegimeScenarioPackJobRequest.model_validate(
        {
            "scenario_pack_id": "CIO_REGIME_2026_Q2",
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-05-03",
            "exposures": [
                {"bucket": "EQUITY", "weight": 0.60},
                {"bucket": "CASH", "weight": 0.40},
            ],
            "exposure_components": components or [],
            "maximum_allowed_loss_pct": 0.12,
        }
    )


def _record() -> ScenarioEvaluationJobRecord:
    return ScenarioEvaluationJobRecord(
        job_id="e1d9cc74-9c67-4b69-a0e5-8ad70e4d14ee",
        tenant_id="tenant-a",
        idempotency_key="scenario-job-001",
        request_fingerprint="sha256:request",
        scenario_pack_id="CIO_REGIME_2026_Q2",
        scenario_pack_revision="sha256:pack",
        immutable_request_json="{}",
        status=ScenarioEvaluationJobStatus.QUEUED,
        actor_id="advisor-a",
        correlation_id="correlation-a",
        claim_token=None,
        lease_expires_at=None,
        attempt_count=0,
        failure_code=None,
        failure_detail=None,
        result_json=None,
        completed_at=None,
        submitted_at=dt.datetime(2026, 5, 3, 9, 30, tzinfo=dt.UTC),
        expires_at=dt.datetime(2026, 5, 6, 9, 30, tzinfo=dt.UTC),
    )


class _RecordingStore:
    def __init__(self, record: ScenarioEvaluationJobRecord | None = None) -> None:
        self.record = record or _record()
        self.submission: dict[str, object] | None = None

    def submit(self, **kwargs: object) -> tuple[ScenarioEvaluationJobRecord, bool]:
        self.submission = kwargs
        return self.record, True

    def get_for_tenant(self, *, tenant_id: str, job_id: str) -> ScenarioEvaluationJobRecord | None:
        if tenant_id == self.record.tenant_id and job_id == self.record.job_id:
            return self.record
        return None


def test_job_request_reconciliation_refuses_duplicate_unknown_and_mismatched_buckets() -> None:
    empty = {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "as_of_date": "2026-05-03",
        "exposures": [],
        "maximum_allowed_loss_pct": 0.12,
    }
    with pytest.raises(ValueError, match="at least one scenario exposure bucket"):
        RegimeScenarioPackJobRequest.model_validate(empty)

    duplicate = {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "as_of_date": "2026-05-03",
        "exposures": [{"bucket": "EQUITY", "weight": 0.50}, {"bucket": "equity", "weight": 0.50}],
        "maximum_allowed_loss_pct": 0.12,
    }
    with pytest.raises(ValueError, match="unique scenario buckets"):
        RegimeScenarioPackJobRequest.model_validate(duplicate)

    with pytest.raises(ValueError, match="buckets absent from exposures"):
        _request(components=[{"security_id": "FI-1", "bucket": "FIXED_INCOME", "weight": 1.0}])

    with pytest.raises(ValueError, match="must reconcile to exposures"):
        _request(components=[{"security_id": "EQ-1", "bucket": "EQUITY", "weight": 0.50}])


def test_canonical_identity_trims_keys_and_is_stable_for_the_same_immutable_request() -> None:
    request = _request()
    assert normalize_idempotency_key(" scenario-job-001 ") == "scenario-job-001"
    assert canonical_request_fingerprint(request) == canonical_request_fingerprint(request)
    assert scenario_pack_revision(request.scenario_pack_id).startswith("sha256:")

    with pytest.raises(ValueError, match="Idempotency-Key is required"):
        normalize_idempotency_key(" \t ")
    with pytest.raises(ValueError, match="must not exceed 128"):
        normalize_idempotency_key("x" * 129)


def test_retention_and_store_configuration_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", raising=False)
    with pytest.raises(ScenarioJobStoreUnavailable, match="positive"):
        retention_hours()
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "0")
    with pytest.raises(ScenarioJobStoreUnavailable, match="positive"):
        retention_hours()
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "48")
    assert retention_hours() == 48

    monkeypatch.delenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", raising=False)
    with pytest.raises(ScenarioJobStoreUnavailable, match="not configured"):
        configured_scenario_job_store()


def test_configured_store_closes_an_unmigrated_store_and_maps_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnmigratedStore:
        closed = False

        def __init__(self, _: str) -> None:
            pass

        def is_schema_ready(self) -> bool:
            return False

        def close(self) -> None:
            self.closed = True

    store = UnmigratedStore("ignored")
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", "sqlite:///ignored.db")
    monkeypatch.setattr(service, "SqlAlchemyScenarioJobStore", lambda _: store)
    with pytest.raises(ScenarioJobStoreUnavailable, match="not migrated or reachable"):
        configured_scenario_job_store()
    assert store.closed is True

    def raise_sqlalchemy_error(_: str) -> None:
        raise SQLAlchemyError("invalid")

    monkeypatch.setattr(service, "SqlAlchemyScenarioJobStore", raise_sqlalchemy_error)
    with pytest.raises(ScenarioJobStoreUnavailable, match="configuration is invalid"):
        configured_scenario_job_store()


def test_store_close_releases_an_isolated_database_engine(tmp_path: Path) -> None:
    store = SqlAlchemyScenarioJobStore(f"sqlite:///{(tmp_path / 'job-store.db').as_posix()}")
    store.close()


def test_submit_preserves_authority_lineage_expiry_and_maps_a_keyed_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "48")
    store = _RecordingStore()
    now = dt.datetime(2026, 5, 3, 9, 30, tzinfo=dt.UTC)
    accepted = submit_scenario_job(
        store=store,  # type: ignore[arg-type]
        tenant_id="tenant-a",
        idempotency_key="scenario-job-001",
        request=_request(),
        actor_id="advisor-a",
        correlation_id="correlation-a",
        now=now,
    )

    assert accepted.job_id == store.record.job_id
    assert store.submission is not None
    assert store.submission["tenant_id"] == "tenant-a"
    assert store.submission["actor_id"] == "advisor-a"
    assert store.submission["correlation_id"] == "correlation-a"
    assert store.submission["expires_at"] == now + dt.timedelta(hours=48)

    class ConflictStore:
        def submit(self, **_: object) -> tuple[ScenarioEvaluationJobRecord, bool]:
            raise ScenarioJobIdempotencyConflict("changed input")

    with pytest.raises(ScenarioJobAdmissionConflict, match="changed input"):
        submit_scenario_job(
            store=ConflictStore(),  # type: ignore[arg-type]
            tenant_id="tenant-a",
            idempotency_key="scenario-job-001",
            request=_request(),
            actor_id=None,
            correlation_id=None,
            now=now,
        )

    unsupported = _request().model_copy(update={"scenario_pack_id": "UNKNOWN"})
    with pytest.raises(ValueError, match="Unsupported scenario_pack_id"):
        submit_scenario_job(
            store=store,  # type: ignore[arg-type]
            tenant_id="tenant-a",
            idempotency_key="scenario-job-001",
            request=unsupported,
            actor_id=None,
            correlation_id=None,
            now=now,
        )


def test_status_mapping_is_tenant_scoped_and_read_store_failure_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _RecordingStore()
    response = scenario_job_status_response(
        store=store,  # type: ignore[arg-type]
        tenant_id="tenant-a",
        job_id=store.record.job_id,
    )
    assert response is not None
    assert response.submitted_at == store.record.submitted_at
    assert (
        scenario_job_status_response(
            store=store,  # type: ignore[arg-type]
            tenant_id="tenant-b",
            job_id=store.record.job_id,
        )
        is None
    )

    monkeypatch.setenv(
        "LOTUS_RISK_SCENARIO_JOB_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'unmigrated.db').as_posix()}",
    )
    with TestClient(app) as client:
        http_response = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{store.record.job_id}",
            headers={"X-Tenant-Id": "tenant-a"},
        )
    assert http_response.status_code == 503


def test_cursor_and_schema_helpers_fail_closed_for_malformed_structures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.scenario_jobs import schema as scenario_job_schema

    assert scenario_job_service._decode_contribution_cursor(
        scenario_job_service._encode_contribution_cursor("growth_slowdown", 0)
    ) == ("growth_slowdown", 0)
    for cursor in ("not-base64", "W10", "WyIiLDAsMV0"):
        with pytest.raises(ValueError, match="cursor is invalid"):
            scenario_job_service._decode_contribution_cursor(cursor)
    assert scenario_job_schema._constraint_columns({"column_names": "job_id"}) == frozenset()

    class _NoContributionTableInspector:
        def has_table(self, _: str) -> bool:
            return False

    assert not scenario_job_schema._has_required_contribution_table(
        cast("Inspector", _NoContributionTableInspector())
    )

    store = SqlAlchemyScenarioJobStore(f"sqlite:///{(tmp_path / 'broken.db').as_posix()}")
    try:
        monkeypatch.setattr(
            scenario_job_schema, "inspect", lambda _: (_ for _ in ()).throw(SQLAlchemyError())
        )
        assert not store.is_schema_ready()
    finally:
        store.close()


def test_status_route_openapi_declares_its_required_tenant_authority() -> None:
    """Generated clients must receive the same ownership requirement as the runtime."""
    operation = app.openapi()["paths"]["/analytics/risk/regime-scenario-pack/jobs/{job_id}"]["get"]
    tenant_parameter = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["in"] == "header" and parameter["name"] == "X-Tenant-Id"
    )

    assert tenant_parameter["required"] is True
    assert tenant_parameter["schema"] == {"type": "string", "minLength": 1, "maxLength": 128}
