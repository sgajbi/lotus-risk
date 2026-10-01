"""Raw-header admission for durable scenario-job ownership and replay identity."""

from fastapi import HTTPException, Request, status

from app.contracts.downstream_authority import TENANT_ID_HEADER
from app.scenario_jobs.identity import normalize_idempotency_key

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


def scenario_job_tenant_id(request: Request) -> str | None:
    """Return the only tenant identity eligible to own a durable scenario job.

    Header scalar access is deliberately not used here: an intermediary must not be able to
    choose an owner by changing duplicate-header ordering.
    """
    return _single_header_value(request, TENANT_ID_HEADER)


def scenario_job_idempotency_key(request: Request) -> str:
    """Return the only replay key eligible to identify an immutable scenario-job submission."""
    value = _single_header_value(request, IDEMPOTENCY_KEY_HEADER)
    if value is None:
        # Preserve the endpoint's existing required-header contract rather than treating an absent
        # key as a normalised empty value.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Idempotency-Key header is required for scenario evaluation job submission",
        )
    return normalize_idempotency_key(value)


def _single_header_value(request: Request, header_name: str) -> str | None:
    values = request.headers.getlist(header_name)
    if len(values) > 1:
        raise ValueError(f"{header_name} must be supplied exactly once")
    return values[0] if values else None


__all__ = ["scenario_job_idempotency_key", "scenario_job_tenant_id"]
