from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace
from typing import cast

import pytest

from app.contracts.scenario_response_outputs import RegimeScenarioPackResponse
from app.scenario_jobs import worker
from app.scenario_jobs.contracts import RegimeScenarioPackJobRequest
from app.scenario_jobs.store import SqlAlchemyScenarioJobStore
from app.services.scenario_engine import evaluate_large_regime_scenario_job


class _Store:
    def __init__(self, claim: object | None = None, *, complete_result: bool = True) -> None:
        self.claim = claim
        self.complete_result = complete_result
        self.closed = False
        self.failed: dict[str, object] | None = None
        self.completed: dict[str, object] | None = None

    def claim_next(self, **_: object) -> object | None:
        return self.claim

    def fail_claim(self, **kwargs: object) -> bool:
        self.failed = kwargs
        return True

    def complete_claim(self, **kwargs: object) -> bool:
        self.completed = kwargs
        return self.complete_result

    def close(self) -> None:
        self.closed = True


def test_worker_once_uses_explicit_operational_limits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _Store()
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(worker, "configured_scenario_job_store", lambda: store)

    def claim(**kwargs: object) -> str:
        calls.append(("claim", kwargs["lease_seconds"]))
        return "job-1"

    def cleanup(**kwargs: object) -> int:
        calls.append(("cleanup", kwargs["limit"]))
        return 2

    monkeypatch.setattr(worker, "process_one_scenario_job", claim)
    monkeypatch.setattr(worker, "cleanup_expired_scenario_jobs", cleanup)

    assert worker.main(["--once", "--lease-seconds", "30", "--cleanup-limit", "5"]) == 0
    assert calls == [("claim", 30), ("cleanup", 5)]
    assert json.loads(capsys.readouterr().out) == {
        "claimed_job_id": "job-1",
        "expired_jobs_deleted": 2,
    }
    assert store.closed


def test_worker_refuses_missing_or_nonpositive_operator_limits() -> None:
    with pytest.raises(SystemExit):
        worker.main(["--once", "--lease-seconds", "0", "--cleanup-limit", "5"])
    with pytest.raises(SystemExit):
        worker.main(["--once", "--lease-seconds", "30"])


def test_worker_returns_idle_without_evaluating_when_no_claim_exists() -> None:
    assert (
        worker.process_one_scenario_job(
            store=cast("SqlAlchemyScenarioJobStore", _Store()), lease_seconds=30
        )
        is None
    )
    with pytest.raises(ValueError, match="positive"):
        worker.process_one_scenario_job(
            store=cast("SqlAlchemyScenarioJobStore", _Store()), lease_seconds=0
        )


def test_worker_records_only_bounded_idle_and_retryable_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes: list[str] = []
    monkeypatch.setattr(
        worker,
        "record_scenario_job_execution",
        lambda *, outcome, started_at: outcomes.append(outcome),
    )
    idle_store = _Store()
    assert (
        worker.process_one_scenario_job(
            store=cast("SqlAlchemyScenarioJobStore", idle_store), lease_seconds=30
        )
        is None
    )

    exploding_store = _Store()
    monkeypatch.setattr(
        exploding_store, "claim_next", lambda **_: (_ for _ in ()).throw(RuntimeError())
    )
    with pytest.raises(RuntimeError):
        worker.process_one_scenario_job(
            store=cast("SqlAlchemyScenarioJobStore", exploding_store), lease_seconds=30
        )
    assert outcomes == ["idle", "retryable_error"]


def test_worker_records_a_qualified_missing_pack_revision_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = SimpleNamespace(
        job_id="job-1",
        claim_token="token-1",
        immutable_request_json=json.dumps(
            {
                "scenario_pack_id": "CIO_REGIME_2026_Q2",
                "as_of_date": "2026-05-03",
                "exposures": [{"bucket": "EQUITY", "weight": 1.0}],
                "exposure_components": [],
                "maximum_allowed_loss_pct": 0.12,
            }
        ),
        scenario_pack_revision="sha256:admitted",
    )
    store = _Store(claim)
    monkeypatch.setattr(worker, "scenario_pack_revision", lambda _: "sha256:missing")

    assert (
        worker.process_one_scenario_job(
            store=cast("SqlAlchemyScenarioJobStore", store), lease_seconds=30
        )
        == "job-1"
    )
    assert store.failed is not None
    assert store.failed["failure_code"] == "SCENARIO_PACK_REVISION_UNAVAILABLE"


def test_worker_publishes_complete_aggregate_or_records_a_stale_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = SimpleNamespace(
        job_id="job-complete",
        claim_token="token-complete",
        immutable_request_json=json.dumps(
            {
                "scenario_pack_id": "CIO_REGIME_2026_Q2",
                "as_of_date": "2026-05-03",
                "exposures": [{"bucket": "EQUITY", "weight": 1.0}],
                "exposure_components": [{"security_id": "EQ-1", "bucket": "EQUITY", "weight": 1.0}],
                "maximum_allowed_loss_pct": 0.12,
            }
        ),
        scenario_pack_revision="sha256:admitted",
    )
    outcomes: list[str] = []
    monkeypatch.setattr(worker, "scenario_pack_revision", lambda _: "sha256:admitted")
    monkeypatch.setattr(
        worker,
        "record_scenario_job_execution",
        lambda *, outcome, started_at: outcomes.append(outcome),
    )
    store = _Store(claim)
    claimed_at = dt.datetime(2026, 5, 3, 9, 30, tzinfo=dt.UTC)
    completed_at = claimed_at + dt.timedelta(seconds=4)
    events: list[str] = []

    def evaluate_after_claim(request: RegimeScenarioPackJobRequest) -> RegimeScenarioPackResponse:
        events.append("evaluate")
        return evaluate_large_regime_scenario_job(request)

    def terminal_clock() -> dt.datetime:
        events.append("terminal-clock")
        return completed_at

    monkeypatch.setattr(worker, "evaluate_large_regime_scenario_job", evaluate_after_claim)
    assert (
        worker.process_one_scenario_job(
            store=cast("SqlAlchemyScenarioJobStore", store),
            now=claimed_at,
            clock=terminal_clock,
        )
        == "job-complete"
    )
    assert store.completed is not None
    assert store.completed["completed_at"] == completed_at
    assert events == ["evaluate", "terminal-clock"]
    aggregate = cast(dict[str, object], store.completed["aggregate_result"])
    assert all(
        result["position_contributions"] == []
        for result in cast(list[dict[str, object]], aggregate["scenario_results"])
    )
    assert len(cast(list[object], store.completed["contributions"])) == 3
    assert outcomes == ["succeeded"]

    stale_store = _Store(claim, complete_result=False)
    assert (
        worker.process_one_scenario_job(store=cast("SqlAlchemyScenarioJobStore", stale_store))
        == "job-complete"
    )
    assert outcomes == ["succeeded", "stale_claim"]


def test_worker_records_invalid_persisted_input_as_a_terminal_failure() -> None:
    claim = SimpleNamespace(
        job_id="job-invalid",
        claim_token="token-invalid",
        immutable_request_json="not-json",
        scenario_pack_revision="sha256:admitted",
    )
    store = _Store(claim)
    claimed_at = dt.datetime(2026, 5, 3, 9, 30, tzinfo=dt.UTC)
    failed_at = claimed_at + dt.timedelta(seconds=2)

    assert (
        worker.process_one_scenario_job(
            store=cast("SqlAlchemyScenarioJobStore", store),
            now=claimed_at,
            lease_seconds=30,
            clock=lambda: failed_at,
        )
        == "job-invalid"
    )
    assert store.failed is not None
    assert store.failed["failure_code"] == "SCENARIO_EVALUATION_INVALID_INPUT"
    assert store.failed["failed_at"] == failed_at


def test_worker_polling_uses_the_explicit_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    intervals: list[int] = []
    monkeypatch.setattr(worker, "configured_scenario_job_store", lambda: store)
    monkeypatch.setattr(worker, "process_one_scenario_job", lambda **_: None)
    monkeypatch.setattr(worker, "cleanup_expired_scenario_jobs", lambda **_: 0)

    def stop_after_one(interval: int) -> None:
        intervals.append(interval)
        raise RuntimeError("stop test polling")

    monkeypatch.setattr("app.scenario_jobs.worker.time.sleep", stop_after_one)
    with pytest.raises(RuntimeError, match="stop test polling"):
        worker.main(["--poll-seconds", "7", "--lease-seconds", "30", "--cleanup-limit", "5"])
    assert intervals == [7]
    assert store.closed


def test_large_worker_evaluator_refuses_an_unknown_immutable_pack() -> None:
    request = RegimeScenarioPackJobRequest.model_validate(
        {
            "scenario_pack_id": "UNKNOWN_PACK",
            "as_of_date": "2026-05-03",
            "exposures": [{"bucket": "EQUITY", "weight": 1.0}],
            "maximum_allowed_loss_pct": 0.12,
        }
    )
    with pytest.raises(ValueError, match="Unsupported scenario_pack_id"):
        evaluate_large_regime_scenario_job(request)
