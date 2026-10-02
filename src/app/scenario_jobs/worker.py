"""Bounded, restart-safe execution of one durable large scenario-evaluation job."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from collections.abc import Callable

from app.contracts.scenario_response_outputs import RegimeScenarioPackResponse
from app.observability import (
    ScenarioJobExecutionOutcome,
    observation_start,
    record_scenario_job_execution,
)
from app.scenario_jobs.contracts import RegimeScenarioPackJobRequest
from app.scenario_jobs.identity import scenario_pack_revision
from app.scenario_jobs.service import configured_scenario_job_store
from app.scenario_jobs.store import (
    ScenarioEvaluationJobContributionRecord,
    ScenarioEvaluationJobRecord,
    SqlAlchemyScenarioJobStore,
)
from app.services.scenario_engine import evaluate_large_regime_scenario_job

DEFAULT_LEASE_SECONDS = 300


def _utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


def process_one_scenario_job(
    *,
    store: SqlAlchemyScenarioJobStore,
    now: dt.datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    clock: Callable[[], dt.datetime] = _utc_now,
) -> str | None:
    """Claim and process at most one job, returning its identity only when claimed.

    Scheduling is intentionally outside this helper: deployment selects its existing worker
    process, while this operation supplies the durable, fenced transaction boundary shared by
    every worker invocation and recovery attempt.
    """
    if lease_seconds <= 0:
        raise ValueError("scenario job lease_seconds must be positive")
    started_at = observation_start()
    outcome: ScenarioJobExecutionOutcome = "retryable_error"
    claimed_at = now or clock()
    try:
        claim = store.claim_next(
            now=claimed_at,
            lease_expires_at=claimed_at + dt.timedelta(seconds=lease_seconds),
        )
    except Exception:
        record_scenario_job_execution(outcome=outcome, started_at=started_at)
        raise
    if claim is None:
        record_scenario_job_execution(outcome="idle", started_at=started_at)
        return None
    assert claim.claim_token is not None
    try:
        outcome = _evaluate_claim(store=store, claim=claim, clock=clock)
    except _QualifiedScenarioJobFailure as exc:
        outcome = _record_claim_failure(
            store=store,
            claim=claim,
            failed_at=clock(),
            failure_code=exc.code,
            failure_detail=exc.code,
            terminal_outcome="qualified_failure",
        )
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        outcome = _record_claim_failure(
            store=store,
            claim=claim,
            failed_at=clock(),
            failure_code="SCENARIO_EVALUATION_INVALID_INPUT",
            failure_detail="Persisted scenario job input could not be evaluated.",
            terminal_outcome="invalid_input",
        )
    finally:
        record_scenario_job_execution(outcome=outcome, started_at=started_at)
    return claim.job_id


def _evaluate_claim(
    *,
    store: SqlAlchemyScenarioJobStore,
    claim: ScenarioEvaluationJobRecord,
    clock: Callable[[], dt.datetime],
) -> ScenarioJobExecutionOutcome:
    """Evaluate one immutable claim and atomically publish it only through its current fence."""
    assert claim.claim_token is not None
    request = RegimeScenarioPackJobRequest.model_validate(json.loads(claim.immutable_request_json))
    if scenario_pack_revision(request.scenario_pack_id) != claim.scenario_pack_revision:
        raise _QualifiedScenarioJobFailure("SCENARIO_PACK_REVISION_UNAVAILABLE")
    evaluation = evaluate_large_regime_scenario_job(request)
    aggregate_result = evaluation.model_copy(
        update={
            "scenario_results": [
                scenario.model_copy(update={"position_contributions": []})
                for scenario in evaluation.scenario_results
            ]
        }
    )
    completed = store.complete_claim(
        job_id=claim.job_id,
        claim_token=claim.claim_token,
        aggregate_result=aggregate_result.model_dump(mode="json"),
        contributions=_contribution_records(job_id=claim.job_id, evaluation=evaluation),
        completed_at=clock(),
    )
    return "succeeded" if completed else "stale_claim"


def _record_claim_failure(
    *,
    store: SqlAlchemyScenarioJobStore,
    claim: ScenarioEvaluationJobRecord,
    failed_at: dt.datetime,
    failure_code: str,
    failure_detail: str,
    terminal_outcome: ScenarioJobExecutionOutcome,
) -> ScenarioJobExecutionOutcome:
    """Fence a qualified terminal failure; a reclaimed claim remains observable as stale."""
    assert claim.claim_token is not None
    failed = store.fail_claim(
        job_id=claim.job_id,
        claim_token=claim.claim_token,
        failure_code=failure_code,
        failure_detail=failure_detail,
        failed_at=failed_at,
    )
    return terminal_outcome if failed else "stale_claim"


def cleanup_expired_scenario_jobs(
    *,
    store: SqlAlchemyScenarioJobStore,
    now: dt.datetime | None = None,
    limit: int = 100,
) -> int:
    """Run one bounded retention batch from the existing worker scheduler."""
    return store.delete_expired(now=now or dt.datetime.now(tz=dt.UTC), limit=limit)


def main(argv: list[str] | None = None) -> int:
    """Run the existing-service scenario worker under an explicit operator schedule."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Process and clean one bounded batch.")
    mode.add_argument(
        "--poll-seconds", type=_positive_int, help="Explicit interval for continuous polling."
    )
    parser.add_argument(
        "--cleanup-limit", type=_positive_int, required=True, help="Maximum expired jobs per batch."
    )
    parser.add_argument(
        "--lease-seconds",
        type=_positive_int,
        required=True,
        help="Claim lease duration for this worker.",
    )
    args = parser.parse_args(argv)
    while True:
        store = configured_scenario_job_store()
        try:
            job_id = process_one_scenario_job(store=store, lease_seconds=args.lease_seconds)
            deleted = cleanup_expired_scenario_jobs(store=store, limit=args.cleanup_limit)
        finally:
            store.close()
        print(json.dumps({"claimed_job_id": job_id, "expired_jobs_deleted": deleted}))
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


class _QualifiedScenarioJobFailure(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def _contribution_records(
    *, job_id: str, evaluation: RegimeScenarioPackResponse
) -> list[ScenarioEvaluationJobContributionRecord]:
    """Flatten the already deterministic engine order into the durable page identity."""
    return [
        ScenarioEvaluationJobContributionRecord(
            job_id=job_id,
            scenario_id=scenario.scenario_id,
            ordinal=ordinal,
            security_id=contribution.security_id,
            display_name=contribution.display_name,
            bucket=contribution.bucket,
            weight=contribution.weight,
            shock_pct=contribution.shock_pct,
            contribution_loss_pct=contribution.contribution_loss_pct,
        )
        for scenario in evaluation.scenario_results
        for ordinal, contribution in enumerate(scenario.position_contributions)
    ]


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_LEASE_SECONDS",
    "cleanup_expired_scenario_jobs",
    "main",
    "process_one_scenario_job",
]
