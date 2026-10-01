from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api_errors import STATEFUL_TENANT_ERROR_RESPONSES
from app.contracts.downstream_authority import admit_downstream_authority
from app.dependencies.request_context import (
    request_actor_id,
    request_correlation_id,
)
from app.openapi_examples import REGIME_SCENARIO_EXAMPLES, request_body_examples
from app.scenario_jobs.contracts import (
    RegimeScenarioPackJobRequest,
    ScenarioEvaluationJobAccepted,
    ScenarioEvaluationJobContributionPage,
    ScenarioEvaluationJobStatusResponse,
)
from app.scenario_jobs.request_headers import scenario_job_idempotency_key, scenario_job_tenant_id
from app.scenario_jobs.service import (
    ScenarioJobAdmissionConflict,
    ScenarioJobStoreUnavailable,
    configured_scenario_job_store,
    scenario_job_contribution_page,
    scenario_job_status_response,
    submit_scenario_job,
)

router = APIRouter(tags=["risk-analytics"])


@router.post(
    "/analytics/risk/regime-scenario-pack/jobs",
    response_model=ScenarioEvaluationJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses=STATEFUL_TENANT_ERROR_RESPONSES,
    operation_id="submitRegimeScenarioPackEvaluationJob",
    summary="Persist a large governed regime scenario evaluation job",
    description=(
        "Admits a tenant-authorized, immutable large scenario evaluation input. A replay with the "
        "same tenant, Idempotency-Key and canonical request returns the original job; changed input "
        "for that key is refused. Exactly one non-blank tenant identity and replay key are required "
        "before admission. Admission is unavailable until the configured relational store has been "
        "migrated."
    ),
    openapi_extra={
        **request_body_examples(REGIME_SCENARIO_EXAMPLES),
        "parameters": [
            {
                "name": "X-Tenant-Id",
                "in": "header",
                "required": True,
                "description": (
                    "Exactly one admitted tenant authority owning the durable job and later reads. "
                    "Duplicate header values are refused."
                ),
                "schema": {"type": "string", "minLength": 1, "maxLength": 128},
                "example": "tenant-sg",
            },
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": True,
                "description": (
                    "Exactly one tenant-scoped replay key for one immutable scenario job submission. "
                    "Duplicate header values are refused."
                ),
                "schema": {"type": "string", "minLength": 1, "maxLength": 128},
                "example": "scenario-job-001",
            },
        ],
    },
)
def submit_regime_scenario_pack_job(
    payload: RegimeScenarioPackJobRequest,
    tenant_id: Annotated[str | None, Depends(scenario_job_tenant_id)],
    actor_id: Annotated[str | None, Depends(request_actor_id)],
    correlation_id: Annotated[str | None, Depends(request_correlation_id)],
    idempotency_key: Annotated[str, Depends(scenario_job_idempotency_key)],
) -> ScenarioEvaluationJobAccepted:
    authority = admit_downstream_authority(tenant_id=tenant_id, correlation_id=correlation_id)
    try:
        store = configured_scenario_job_store()
    except ScenarioJobStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    try:
        return submit_scenario_job(
            store=store,
            tenant_id=authority.tenant_id,
            idempotency_key=idempotency_key,
            request=payload,
            actor_id=actor_id,
            correlation_id=authority.correlation_id,
        )
    except ScenarioJobAdmissionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    finally:
        store.close()


@router.get(
    "/analytics/risk/regime-scenario-pack/jobs/{job_id}",
    response_model=ScenarioEvaluationJobStatusResponse,
    responses=STATEFUL_TENANT_ERROR_RESPONSES,
    operation_id="getRegimeScenarioPackEvaluationJob",
    summary="Read the submitting tenant's scenario evaluation job posture",
    description=(
        "Returns one admitted job only to its submitting tenant. Exactly one non-blank tenant "
        "identity is required. Unknown and foreign job ids both return not found. A `QUEUED` record "
        "is retained admission evidence, not completed analysis."
    ),
    openapi_extra={
        "parameters": [
            {
                "name": "X-Tenant-Id",
                "in": "header",
                "required": True,
                "description": (
                    "Exactly one admitted tenant authority that owns the durable job. "
                    "Duplicate header values are refused."
                ),
                "schema": {"type": "string", "minLength": 1, "maxLength": 128},
                "example": "tenant-sg",
            }
        ]
    },
)
def get_regime_scenario_pack_job(
    job_id: str,
    tenant_id: Annotated[str | None, Depends(scenario_job_tenant_id)],
    correlation_id: Annotated[str | None, Depends(request_correlation_id)],
) -> ScenarioEvaluationJobStatusResponse:
    authority = admit_downstream_authority(tenant_id=tenant_id, correlation_id=correlation_id)
    try:
        store = configured_scenario_job_store()
    except ScenarioJobStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    try:
        response = scenario_job_status_response(
            store=store,
            tenant_id=authority.tenant_id,
            job_id=job_id,
        )
    finally:
        store.close()
    if response is None:
        # Deliberately indistinguishable from an absent record so tenant boundaries do not disclose ids.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scenario evaluation job not found"
        )
    return response


@router.get(
    "/analytics/risk/regime-scenario-pack/jobs/{job_id}/contributions",
    response_model=ScenarioEvaluationJobContributionPage,
    responses=STATEFUL_TENANT_ERROR_RESPONSES,
    operation_id="getRegimeScenarioPackEvaluationJobContributions",
    summary="Read a stable page of completed scenario-job contributions",
    description=(
        "Returns only immutable rows committed with a successful evaluation for the submitting "
        "tenant. Queued, running, failed, unknown, and foreign jobs do not expose contributions."
    ),
    openapi_extra={
        "parameters": [
            {
                "name": "X-Tenant-Id",
                "in": "header",
                "required": True,
                "description": "Exactly one admitted tenant authority owning the durable job.",
                "schema": {"type": "string", "minLength": 1, "maxLength": 128},
                "example": "tenant-sg",
            }
        ]
    },
)
def get_regime_scenario_pack_job_contributions(
    job_id: str,
    tenant_id: Annotated[str | None, Depends(scenario_job_tenant_id)],
    correlation_id: Annotated[str | None, Depends(request_correlation_id)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> ScenarioEvaluationJobContributionPage:
    authority = admit_downstream_authority(tenant_id=tenant_id, correlation_id=correlation_id)
    try:
        store = configured_scenario_job_store()
    except ScenarioJobStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    try:
        response = scenario_job_contribution_page(
            store=store,
            tenant_id=authority.tenant_id,
            job_id=job_id,
            cursor=cursor,
            limit=limit,
        )
    finally:
        store.close()
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario evaluation job contributions not found",
        )
    return response
