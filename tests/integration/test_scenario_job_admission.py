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


def _all_equity_component_payload(component_count: int) -> dict[str, object]:
    components = [
        {"security_id": f"EQ-{index:04d}", "bucket": "EQUITY", "weight": 0.001}
        for index in range(component_count)
    ]
    component_weight = 1 / component_count
    for component in components:
        component["weight"] = component_weight
    return {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "as_of_date": "2026-05-03",
        "exposures": [{"bucket": "EQUITY", "weight": 1.0}],
        "exposure_components": components,
        "maximum_allowed_loss_pct": 0.12,
    }


def _large_payload() -> dict[str, object]:
    return _all_equity_component_payload(1_000)


def _apply_migration(database_url: str, revision: str = "head") -> None:
    environment = os.environ.copy()
    environment["LOTUS_RISK_SCENARIO_JOB_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def _reset_explicitly_isolated_postgres_job_schema(database_url: str) -> None:
    """Remove only prior Alembic job-schema state from the opt-in disposable PostgreSQL target."""
    environment = os.environ.copy()
    environment["LOTUS_RISK_SCENARIO_JOB_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
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


def test_large_job_worker_persists_all_contributions_once_and_pages_them_stably(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A durable worker never asks consumers to rebuild the 1,000-security evaluation."""
    database_url = _migrated_database(tmp_path, monkeypatch)
    headers = {"X-Tenant-Id": "tenant-large", "Idempotency-Key": "large-scenario-001"}
    with TestClient(app) as client:
        admitted = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_large_payload(), headers=headers
        )
    assert admitted.status_code == 202
    job_id = admitted.json()["job_id"]

    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore
    from app.scenario_jobs.worker import process_one_scenario_job

    store = SqlAlchemyScenarioJobStore(database_url)
    try:
        assert (
            process_one_scenario_job(store=store, now=dt.datetime(2026, 5, 3, 10, 0, tzinfo=dt.UTC))
            == job_id
        )
        assert (
            process_one_scenario_job(store=store, now=dt.datetime(2026, 5, 3, 10, 1, tzinfo=dt.UTC))
            is None
        )
    finally:
        store.close()

    seen: list[tuple[str, str]] = []
    contribution_totals: dict[str, float] = {}
    cursor: str | None = None
    with TestClient(app) as client:
        status_response = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{job_id}",
            headers={"X-Tenant-Id": "tenant-large"},
        )
        foreign_page = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{job_id}/contributions",
            headers={"X-Tenant-Id": "tenant-other"},
        )
        while True:
            page = client.get(
                f"/analytics/risk/regime-scenario-pack/jobs/{job_id}/contributions",
                headers={"X-Tenant-Id": "tenant-large"},
                params={"limit": 250, **({"cursor": cursor} if cursor else {})},
            )
            assert page.status_code == 200
            payload = page.json()
            seen.extend(
                (row["scenario_id"], row["security_id"]) for row in payload["contributions"]
            )
            for row in payload["contributions"]:
                contribution_totals[row["scenario_id"]] = (
                    contribution_totals.get(row["scenario_id"], 0.0) + row["contribution_loss_pct"]
                )
            cursor = payload["next_cursor"]
            if cursor is None:
                break

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "SUCCEEDED"
    assert all(
        not item["position_contributions"]
        for item in status_response.json()["result"]["scenario_results"]
    )
    expected_losses = {
        scenario["scenario_id"]: scenario["expected_loss_pct"]
        for scenario in status_response.json()["result"]["scenario_results"]
    }
    assert expected_losses == pytest.approx(
        {"growth_slowdown": 0.12, "rates_up_inflation": 0.08, "risk_off_liquidity": 0.18}
    )
    assert contribution_totals == pytest.approx(expected_losses)
    assert foreign_page.status_code == 404
    assert len(seen) == 3_000
    assert len(set(seen)) == 3_000


def test_sync_boundary_preserves_83_component_path_and_admits_84_to_the_durable_route(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The durable route expands explainability without weakening the synchronous response cap."""
    _migrated_database(tmp_path, monkeypatch)
    with TestClient(app) as client:
        synchronous = client.post(
            "/analytics/risk/regime-scenario-pack/evaluate",
            json=_all_equity_component_payload(83),
        )
        over_sync_bound = client.post(
            "/analytics/risk/regime-scenario-pack/evaluate",
            json=_all_equity_component_payload(84),
        )
        durable = client.post(
            "/analytics/risk/regime-scenario-pack/jobs",
            json=_all_equity_component_payload(84),
            headers={"X-Tenant-Id": "tenant-boundary", "Idempotency-Key": "84-components"},
        )

    assert synchronous.status_code == 200
    assert (
        sum(
            len(scenario["position_contributions"])
            for scenario in synchronous.json()["scenario_results"]
        )
        == 249
    )
    assert over_sync_bound.status_code == 400
    assert durable.status_code == 202
    assert durable.json()["status"] == "QUEUED"


def test_expiry_cleanup_is_bounded_and_preserves_nonexpired_tenant_evidence(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_url = _migrated_database(tmp_path, monkeypatch)
    from app.scenario_jobs.contracts import RegimeScenarioPackJobRequest
    from app.scenario_jobs.service import submit_scenario_job
    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore
    from app.scenario_jobs.worker import cleanup_expired_scenario_jobs

    request = RegimeScenarioPackJobRequest.model_validate(_payload())
    cleanup_at = dt.datetime(2026, 5, 10, 9, 0, tzinfo=dt.UTC)
    store = SqlAlchemyScenarioJobStore(database_url)
    try:
        expired_first = submit_scenario_job(
            store=store,
            tenant_id="tenant-cleanup",
            idempotency_key="expired-first",
            request=request,
            actor_id=None,
            correlation_id=None,
            now=cleanup_at - dt.timedelta(days=5),
        )
        expired_second = submit_scenario_job(
            store=store,
            tenant_id="tenant-cleanup",
            idempotency_key="expired-second",
            request=request,
            actor_id=None,
            correlation_id=None,
            now=cleanup_at - dt.timedelta(days=4),
        )
        retained = submit_scenario_job(
            store=store,
            tenant_id="tenant-cleanup",
            idempotency_key="retained",
            request=request,
            actor_id=None,
            correlation_id=None,
            now=cleanup_at - dt.timedelta(days=1),
        )
        assert cleanup_expired_scenario_jobs(store=store, now=cleanup_at, limit=1) == 1
        assert store.get_for_tenant(tenant_id="tenant-cleanup", job_id=expired_first.job_id) is None
        assert (
            store.get_for_tenant(tenant_id="tenant-cleanup", job_id=expired_second.job_id)
            is not None
        )
        assert store.get_for_tenant(tenant_id="tenant-cleanup", job_id=retained.job_id) is not None
        assert cleanup_expired_scenario_jobs(store=store, now=cleanup_at, limit=10) == 1
        assert (
            store.get_for_tenant(tenant_id="tenant-cleanup", job_id=expired_second.job_id) is None
        )
        assert store.get_for_tenant(tenant_id="tenant-cleanup", job_id=retained.job_id) is not None
    finally:
        store.close()


def test_contribution_route_refuses_invalid_cursor_and_unavailable_store(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    _migrated_database(tmp_path, monkeypatch)
    headers = {"X-Tenant-Id": "tenant-page", "Idempotency-Key": "page-001"}
    with TestClient(app) as client:
        admitted = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        assert admitted.status_code == 202
        invalid_cursor = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{admitted.json()['job_id']}/contributions",
            headers={"X-Tenant-Id": "tenant-page"},
            params={"cursor": "not-a-valid-cursor"},
        )
    assert invalid_cursor.status_code == 400

    monkeypatch.setenv(
        "LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", f"sqlite:///{(tmp_path / 'missing.db').as_posix()}"
    )
    with TestClient(app) as client:
        unavailable = client.get(
            "/analytics/risk/regime-scenario-pack/jobs/not-present/contributions",
            headers={"X-Tenant-Id": "tenant-page"},
        )
    assert unavailable.status_code == 503


def test_scenario_job_routes_refuse_the_previous_schema_until_operator_upgrade(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A table from the prior migration is not evidence that this ORM can serve job traffic."""
    database_url = f"sqlite:///{(tmp_path / 'previous-schema.db').as_posix()}"
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _apply_migration(database_url, "20261001_01")
    headers = {"X-Tenant-Id": "upgrade-tenant", "Idempotency-Key": "upgrade-001"}

    with TestClient(app) as client:
        unavailable_submit = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        unavailable_read = client.get(
            "/analytics/risk/regime-scenario-pack/jobs/not-present",
            headers={"X-Tenant-Id": "upgrade-tenant"},
        )

    assert unavailable_submit.status_code == 503
    assert unavailable_read.status_code == 503
    from sqlalchemy import create_engine, text

    prior_schema_engine = create_engine(database_url)
    try:
        with prior_schema_engine.connect() as connection:
            assert (
                connection.execute(text("select count(*) from scenario_evaluation_jobs")).scalar()
                == 0
            )
    finally:
        prior_schema_engine.dispose()

    _apply_migration(database_url)
    with TestClient(app) as client:
        admitted = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        replay = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        owner_read = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{admitted.json()['job_id']}",
            headers={"X-Tenant-Id": "upgrade-tenant"},
        )
        foreign_read = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{admitted.json()['job_id']}",
            headers={"X-Tenant-Id": "other-tenant"},
        )

    assert admitted.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == admitted.json()
    assert owner_read.status_code == 200
    assert foreign_read.status_code == 404


def test_schema_readiness_allows_a_compatible_future_addition(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'future-schema.db').as_posix()}"
    _apply_migration(database_url)
    from sqlalchemy import create_engine, text

    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "alter table scenario_evaluation_jobs add column future_producer_revision text"
                )
            )
    finally:
        engine.dispose()

    store = SqlAlchemyScenarioJobStore(database_url)
    try:
        assert store.is_schema_ready()
    finally:
        store.close()


def test_schema_readiness_refuses_job_columns_without_durable_key_constraints(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'missing-key-constraints.db').as_posix()}"
    _apply_migration(database_url)
    from sqlalchemy import create_engine, text

    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "create table scenario_evaluation_jobs_without_keys as "
                    "select * from scenario_evaluation_jobs"
                )
            )
            connection.execute(text("drop table scenario_evaluation_jobs"))
            connection.execute(
                text(
                    "alter table scenario_evaluation_jobs_without_keys "
                    "rename to scenario_evaluation_jobs"
                )
            )
    finally:
        engine.dispose()

    store = SqlAlchemyScenarioJobStore(database_url)
    try:
        assert not store.is_schema_ready()
    finally:
        store.close()


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

    conflict_inspection_engine = create_engine(f"sqlite:///{database_path}")
    try:
        with conflict_inspection_engine.connect() as connection:
            rows = connection.execute(
                text("select immutable_request_json from scenario_evaluation_jobs")
            ).all()
    finally:
        conflict_inspection_engine.dispose()
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


@pytest.mark.parametrize(
    ("headers", "status_code", "error_code", "message"),
    [
        (
            {"X-Tenant-Id": " ", "Idempotency-Key": "blank-tenant"},
            401,
            "MISSING_TENANT_AUTHORITY",
            "Stateful input requires X-Tenant-Id before any upstream request is made.",
        ),
        (
            {"X-Tenant-Id": "t" * 129, "Idempotency-Key": "oversized-tenant"},
            400,
            "INVALID_TENANT_AUTHORITY",
            "X-Tenant-Id must not exceed 128 characters after trimming.",
        ),
        (
            {"X-Tenant-Id": "tenant-a", "Idempotency-Key": " \t "},
            400,
            "INVALID_INPUT",
            "Idempotency-Key is required for scenario evaluation job submission",
        ),
        (
            {"X-Tenant-Id": "tenant-a", "Idempotency-Key": "k" * 129},
            400,
            "INVALID_INPUT",
            "Idempotency-Key must not exceed 128 characters after trimming",
        ),
    ],
)
def test_job_admission_preserves_single_header_value_validation(
    headers: dict[str, str], status_code: int, error_code: str, message: str
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert response.json()["error"]["message"] == message


@pytest.mark.parametrize(
    ("headers", "header_name"),
    [
        (
            [
                ("X-Tenant-Id", "tenant-a"),
                ("x-tenant-id", "tenant-a"),
                ("Idempotency-Key", "duplicate-tenant-same"),
            ],
            "X-Tenant-Id",
        ),
        (
            [
                ("x-tenant-id", "tenant-b"),
                ("X-Tenant-Id", "tenant-a"),
                ("Idempotency-Key", "duplicate-tenant-reversed"),
            ],
            "X-Tenant-Id",
        ),
        (
            [
                ("X-Tenant-Id", "tenant-a"),
                ("Idempotency-Key", "duplicate-key-same"),
                ("idempotency-key", "duplicate-key-same"),
            ],
            "Idempotency-Key",
        ),
        (
            [
                ("X-Tenant-Id", "tenant-a"),
                ("idempotency-key", "duplicate-key-b"),
                ("Idempotency-Key", "duplicate-key-a"),
            ],
            "Idempotency-Key",
        ),
    ],
)
def test_job_admission_refuses_ambiguous_raw_headers_without_a_durable_write(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    headers: list[tuple[str, str]],
    header_name: str,
) -> None:
    database_url = _migrated_database(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert response.json()["error"]["message"] == f"{header_name} must be supplied exactly once"

    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("select count(*) from scenario_evaluation_jobs")) == 0
    finally:
        engine.dispose()


def test_job_routes_refuse_ambiguous_tenant_before_opening_the_store(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.routers import scenario_jobs as scenario_jobs_router

    def store_must_not_open() -> object:
        raise AssertionError(
            "ambiguous tenant authority must be rejected before store construction"
        )

    monkeypatch.setattr(scenario_jobs_router, "configured_scenario_job_store", store_must_not_open)
    ambiguous_tenant_headers = [
        ("X-Tenant-Id", "tenant-a"),
        ("x-tenant-id", "tenant-b"),
        ("Idempotency-Key", "store-guard"),
    ]
    with TestClient(app) as client:
        submission = client.post(
            "/analytics/risk/regime-scenario-pack/jobs",
            json=_payload(),
            headers=ambiguous_tenant_headers,
        )
        status_read = client.get(
            "/analytics/risk/regime-scenario-pack/jobs/not-a-job",
            headers=ambiguous_tenant_headers,
        )

    for response in (submission, status_read):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_INPUT"
        assert response.json()["error"]["message"] == "X-Tenant-Id must be supplied exactly once"


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
    from app.scenario_jobs.store import ScenarioEvaluationJobContributionRecord

    assert not store.complete_claim(
        job_id=first_claim.job_id,
        claim_token=first_claim.claim_token,
        aggregate_result={"must_not": "publish"},
        contributions=[
            ScenarioEvaluationJobContributionRecord(
                job_id=first_claim.job_id,
                scenario_id="growth_slowdown",
                ordinal=0,
                security_id="STALE",
                display_name=None,
                bucket="EQUITY",
                weight=1.0,
                shock_pct=-0.12,
                contribution_loss_pct=0.12,
            )
        ],
        completed_at=reclaimed_at,
    )
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


def test_store_refuses_invalid_claim_cleanup_and_contribution_ownership(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_url = _migrated_database(tmp_path, monkeypatch)
    from app.scenario_jobs.contracts import RegimeScenarioPackJobRequest
    from app.scenario_jobs.service import submit_scenario_job
    from app.scenario_jobs.store import (
        ScenarioEvaluationJobContributionRecord,
        SqlAlchemyScenarioJobStore,
    )

    store = SqlAlchemyScenarioJobStore(database_url)
    now = dt.datetime(2026, 5, 3, 9, 0, tzinfo=dt.UTC)
    try:
        with pytest.raises(ValueError, match="after"):
            store.claim_next(now=now, lease_expires_at=now)
        with pytest.raises(ValueError, match="positive"):
            store.delete_expired(now=now, limit=0)
        assert store.delete_expired(now=now, limit=1) == 0

        request = RegimeScenarioPackJobRequest.model_validate(_payload())
        admitted = submit_scenario_job(
            store=store,
            tenant_id="tenant-store",
            idempotency_key="store-ownership",
            request=request,
            actor_id=None,
            correlation_id=None,
            now=now,
        )
        claim = store.claim_next(now=now, lease_expires_at=now + dt.timedelta(minutes=5))
        assert claim is not None and claim.claim_token is not None
        with pytest.raises(ValueError, match="does not belong"):
            store.complete_claim(
                job_id=admitted.job_id,
                claim_token=claim.claim_token,
                aggregate_result={},
                contributions=[
                    ScenarioEvaluationJobContributionRecord(
                        job_id="other-job",
                        scenario_id="growth_slowdown",
                        ordinal=0,
                        security_id="EQ-1",
                        display_name=None,
                        bucket="EQUITY",
                        weight=1.0,
                        shock_pct=-0.12,
                        contribution_loss_pct=0.12,
                    )
                ],
                completed_at=now,
            )
    finally:
        store.close()


@pytest.mark.skipif(
    not os.getenv("LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"),
    reason="requires an explicitly provisioned isolated PostgreSQL URL",
)
def test_postgres_job_admission_replays_after_migration(monkeypatch: MonkeyPatch) -> None:
    """Real PostgreSQL proof; never targets canonical runtime data or a shared database."""
    database_url = os.environ["LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"]
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _reset_explicitly_isolated_postgres_job_schema(database_url)
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
def test_postgres_job_routes_refuse_the_previous_schema_until_operator_upgrade(
    monkeypatch: MonkeyPatch,
) -> None:
    """PostgreSQL has the same no-traffic-before-migration refusal as SQLite."""
    database_url = os.environ["LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"]
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _reset_explicitly_isolated_postgres_job_schema(database_url)
    _apply_migration(database_url, "20261001_01")
    headers = {"X-Tenant-Id": "postgres-upgrade-tenant", "Idempotency-Key": "postgres-upgrade"}

    with TestClient(app) as client:
        unavailable_submit = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        unavailable_read = client.get(
            "/analytics/risk/regime-scenario-pack/jobs/not-present",
            headers={"X-Tenant-Id": "postgres-upgrade-tenant"},
        )

    assert unavailable_submit.status_code == 503
    assert unavailable_read.status_code == 503
    _apply_migration(database_url)
    with TestClient(app) as client:
        admitted = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )
        replay = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_payload(), headers=headers
        )

    assert admitted.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == admitted.json()


@pytest.mark.skipif(
    not os.getenv("LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"),
    reason="requires an explicitly provisioned isolated PostgreSQL URL",
)
def test_postgres_concurrent_claims_do_not_share_a_job(monkeypatch: MonkeyPatch) -> None:
    """Concurrent workers use PostgreSQL row locks to claim distinct durable jobs."""
    database_url = os.environ["LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"]
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _reset_explicitly_isolated_postgres_job_schema(database_url)
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


@pytest.mark.skipif(
    not os.getenv("LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"),
    reason="requires an explicitly provisioned isolated PostgreSQL URL",
)
def test_postgres_worker_commits_large_result_and_complete_pages(monkeypatch: MonkeyPatch) -> None:
    """Real PostgreSQL transaction proof for the 1,000-security success boundary."""
    database_url = os.environ["LOTUS_RISK_SCENARIO_JOB_POSTGRES_URL"]
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_DATABASE_URL", database_url)
    monkeypatch.setenv("LOTUS_RISK_SCENARIO_JOB_RETENTION_HOURS", "72")
    _reset_explicitly_isolated_postgres_job_schema(database_url)
    _apply_migration(database_url)
    headers = {"X-Tenant-Id": "postgres-large", "Idempotency-Key": "postgres-large-001"}
    with TestClient(app) as client:
        admitted = client.post(
            "/analytics/risk/regime-scenario-pack/jobs", json=_large_payload(), headers=headers
        )
    assert admitted.status_code == 202
    job_id = admitted.json()["job_id"]

    from app.scenario_jobs.store import SqlAlchemyScenarioJobStore
    from app.scenario_jobs.worker import process_one_scenario_job

    store = SqlAlchemyScenarioJobStore(database_url)
    try:
        assert process_one_scenario_job(store=store) == job_id
        assert (
            store.contribution_page(
                tenant_id="postgres-large", job_id=job_id, after=None, limit=3_000
            )
            is not None
        )
        assert (
            len(
                store.contribution_page(
                    tenant_id="postgres-large", job_id=job_id, after=None, limit=3_000
                )
                or []
            )
            == 3_000
        )
    finally:
        store.close()

    with TestClient(app) as client:
        status_response = client.get(
            f"/analytics/risk/regime-scenario-pack/jobs/{job_id}", headers=headers
        )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "SUCCEEDED"
