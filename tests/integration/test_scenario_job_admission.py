from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import app


def _payload(*, maximum_allowed_loss_pct: float = 0.12) -> dict[str, object]:
    return {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "as_of_date": "2026-05-03",
        "exposures": [
            {"bucket": "EQUITY", "weight": 0.55},
            {"bucket": "FIXED_INCOME", "weight": 0.35},
            {"bucket": "CASH", "weight": 0.10},
        ],
        "exposure_components": [
            {"security_id": "EQ-1", "bucket": "EQUITY", "weight": 0.55},
            {"security_id": "FI-1", "bucket": "FIXED_INCOME", "weight": 0.35},
            {"security_id": "CASH-1", "bucket": "CASH", "weight": 0.10},
        ],
        "maximum_allowed_loss_pct": maximum_allowed_loss_pct,
    }


def _apply_migration(database_url: str) -> None:
    environment = os.environ.copy()
    environment["LOTUS_RISK_SCENARIO_JOB_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def _migrated_database(tmp_path: Path, monkeypatch: MonkeyPatch) -> str:
    database_url = f"sqlite:///{(tmp_path / 'scenario-jobs.db').as_posix()}"
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _apply_migration(database_url)
    return database_url


def test_sqlite_migrated_job_admission_replays_immutable_input_and_hides_foreign_job(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    _migrated_database(tmp_path, monkeypatch)
    headers = {"X-Tenant-Id": "tenant-a", "Idempotency-Key": "scenario-job-001"}
    with TestClient(app) as client:
        created = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        replay = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )

        assert created.status_code == 202
        assert replay.status_code == 202
        assert replay.json() == created.json()
        job_id = created.json()["job_id"]
        assert created.json()["status"] == "QUEUED"
        assert created.json()["request_fingerprint"].startswith("sha256:")
        assert created.json()["scenario_pack_revision"].startswith("sha256:")

        owner_read = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{job_id}",
            headers={"X-Tenant-Id": "tenant-a"},
        )
        foreign_read = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{job_id}",
            headers={"X-Tenant-Id": "tenant-b"},
        )

    assert owner_read.status_code == 200
    assert owner_read.json()["job_id"] == job_id
    assert foreign_read.status_code == 404

    # A fresh client/engine reads the same durable SQLite record; there is no process-local replay cache.
    with TestClient(app) as restarted_client:
        after_restart = restarted_client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{job_id}",
            headers={"X-Tenant-Id": "tenant-a"},
        )
    assert after_restart.status_code == 200
    assert after_restart.json() == owner_read.json()


def test_job_admission_refuses_changed_payload_for_same_tenant_key_without_second_write(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_url = _migrated_database(tmp_path, monkeypatch)
    headers = {"X-Tenant-Id": "tenant-a", "Idempotency-Key": "scenario-job-conflict"}
    with TestClient(app) as client:
        first = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        conflict = client.post(
            "/analytics/risk/regime-scenario-pack/jobs",
            json=_payload(maximum_allowed_loss_pct=0.11),
            headers=headers,
        )

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert "different scenario job input" in conflict.json()["error"]["message"]

    database_path = database_url.removeprefix("sqlite:///")
    from sqlalchemy import create_engine, text

    with create_engine(f"sqlite:///{database_path}").connect() as connection:
        rows = connection.execute(
            text("select immutable_request_json from scenario_evaluation_jobs")
        ).all()
    assert len(rows) == 1
    assert json.loads(rows[0][0])["maximum_allowed_loss_pct"] == 0.12


def test_large_job_contract_accepts_one_thousand_reconciled_components() -> None:
    components = [
        {
            "security_id": f"EQ-{ordinal:04d}",
            "display_name": f"Equity {ordinal:04d}",
            "bucket": "EQUITY",
            "weight": 0.001,
        }
        for ordinal in range(1_000)
    ]
    payload = {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "as_of_date": "2026-05-03",
        "exposures": [{"bucket": "EQUITY", "weight": 1.0}],
        "exposure_components": components,
        "maximum_allowed_loss_pct": 0.12,
    }

    from app.scenario_jobs.contracts import RegimeScenarioPackJobRequest

    parsed = RegimeScenarioPackJobRequest.model_validate(payload)
    assert len(parsed.exposure_components) == 1_000


def test_job_admission_refuses_missing_authority_or_idempotency_before_store_access() -> None:
    with TestClient(app) as client:
        missing_tenant = client.post(
            "/analytics/risk/regime-scenario-pack/jobs",
            json=_payload(),
            headers={"Idempotency-Key": "missing-tenant"},
        )
        missing_key = client.post(
            "/analytics/risk/regime-scenario-pack/jobs",
            json=_payload(),
            headers={"X-Tenant-Id": "tenant-a"},
        )

    assert missing_tenant.status_code == 401
    assert missing_tenant.json()["error"]["code"] == "MISSING_TENANT_AUTHORITY"
    assert missing_key.status_code == 422
    assert missing_key.json()["error"]["code"] == "INVALID_REQUEST"


def test_job_admission_refuses_an_unmigrated_configured_store(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "LOTUS_RISK_SCENARIO_JOB_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'unmigrated.db').as_posix()}",
    )
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    with TestClient(app) as client:
        response = client.post(
            "/analytics/risk/regime-scenario-pack/jobs",
            json=_payload(),
            headers={"X-Tenant-Id": "tenant-a", "Idempotency-Key": "unmigrated-store"},
        )

    assert response.status_code == 503
    assert "not migrated or reachable" in response.json()["error"]["message"]


def test_expired_claim_is_recovered_with_a_new_token_and_stale_failure_is_fenced(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    _migrated_database(tmp_path, monkeypatch)
    headers = {"X-Tenant-Id": "tenant-a", "Idempotency-Key": "scenario-job-claim"}
    with TestClient(app) as client:
        admitted = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
    assert admitted.status_code == 202

    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore

    store = SqlAlchemyScenarioJobStore(os.environ["LOTUS_RISK_SCENARIO_JOB_DATABASE_URL"])
    claimed_at = dt.datetime(2026, 5, 3, 9, 30, tzinfo=dt.UTC)
    first_claim = store.claim_next(
        now=claimed_at,
        lease_expires_at=claimed_at + dt.timedelta(minutes=5),
    )
    assert first_claim is not None
    assert first_claim.status.value == "RUNNING"
    assert first_claim.attempt_count == 1
    assert first_claim.claim_token is not None
    assert (
        store.claim_next(
            now=claimed_at + dt.timedelta(minutes=1),
            lease_expires_at=claimed_at + dt.timedelta(minutes=6),
        )
        is None
    )

    reclaimed_at = claimed_at + dt.timedelta(minutes=6)
    recovered_claim = store.claim_next(
        now=reclaimed_at,
        lease_expires_at=reclaimed_at + dt.timedelta(minutes=5),
    )
    assert recovered_claim is not None
    assert recovered_claim.claim_token is not None
    assert recovered_claim.claim_token != first_claim.claim_token
    assert recovered_claim.attempt_count == 2
    assert not store.fail_claim(
        job_id=first_claim.job_id,
        claim_token=first_claim.claim_token,
        failure_code="STALE_WORKER",
        failure_detail="must not overwrite the reclaimed claim",
        failed_at=reclaimed_at,
    )
    assert store.fail_claim(
        job_id=recovered_claim.job_id,
        claim_token=recovered_claim.claim_token,
        failure_code="SCENARIO_PACK_REVISION_UNAVAILABLE",
        failure_detail="persisted revision was unavailable to the evaluator",
        failed_at=reclaimed_at,
    )
    store.close()

    with TestClient(app) as client:
        status_response = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{admitted.json()['job_id']}",
            headers={"X-Tenant-Id": "tenant-a"},
        )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "FAILED"
    assert status_response.json()["failure_code"] == "SCENARIO_PACK_REVISION_UNAVAILABLE"


@pytest.mark.skipif(
    not os.getenv("LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"),
    reason="requires an explicitly provisioned isolated PostgreSQL URL",
)
def test_postgres_job_admission_replays_after_migration(monkeypatch: MonkeyPatch) -> None:
    """Real PostgreSQL proof; never targets canonical runtime data or a shared database."""
    database_url = os.environ["LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"]
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _apply_migration(database_url)
    headers = {"X-Tenant-Id": "postgres-tenant", "Idempotency-Key": "postgres-replay"}
    with TestClient(app) as client:
        first = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        replay = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == first.json()

    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore

    store = SqlAlchemyScenarioJobStore(database_url)
    claimed_at = dt.datetime(2026, 5, 3, 9, 0, tzinfo=dt.UTC)
    try:
        claim = store.claim_next(
            now=claimed_at,
            lease_expires_at=claimed_at + dt.timedelta(minutes=5),
        )
        assert claim is not None
        assert claim.job_id == first.json()["job_id"]
        assert claim.claim_token is not None
        assert store.fail_claim(
            job_id=claim.job_id,
            claim_token=claim.claim_token,
            failure_code="POSTGRES_TEST_TERMINAL",
            failure_detail="releases the isolated replay fixture from the runnable queue",
            failed_at=claimed_at,
        )
    finally:
        store.close()


@pytest.mark.skipif(
    not os.getenv("LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"),
    reason="requires an explicitly provisioned isolated PostgreSQL URL",
)
def test_postgres_concurrent_claims_do_not_share_a_job(monkeypatch: MonkeyPatch) -> None:
    """Concurrent workers use PostgreSQL row locks to claim distinct durable jobs."""
    database_url = os.environ["LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"]
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _apply_migration(database_url)
    request_prefix = f"postgres-claim-{uuid4()}"
    headers = [
        {"X-Tenant-Id": "postgres-claim-tenant", "Idempotency-Key": f"{request_prefix}-{index}"}
        for index in range(2)
    ]
    with TestClient(app) as client:
        admitted = [
            client.post(
                "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=header
            )
            for header in headers
        ]
    assert [response.status_code for response in admitted] == [202, 202]
    submitted_job_ids = {response.json()["job_id"] for response in admitted}

    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore

    claimed_at = dt.datetime(2026, 5, 3, 10, 0, tzinfo=dt.UTC)
    lease_expires_at = claimed_at + dt.timedelta(minutes=5)
    stores = [SqlAlchemyScenarioJobStore(database_url) for _ in range(2)]
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            claims = list(
                executor.map(
                    lambda store: store.claim_next(
                        now=claimed_at, lease_expires_at=lease_expires_at
                    ),
                    stores,
                )
            )
    finally:
        for store in stores:
            store.close()

    assert all(claim is not None for claim in claims)
    durable_claims = [claim for claim in claims if claim is not None]
    assert {claim.job_id for claim in durable_claims} == submitted_job_ids
    assert len({claim.claim_token for claim in durable_claims}) == 2
    assert {claim.attempt_count for claim in durable_claims} == {1}
