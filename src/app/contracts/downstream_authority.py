"""Admitted tenant authority carried from the registered route to downstream producers.

Stateful analytics read tenant-owned data from lotus-performance and lotus-core, and those
producers refuse stateful requests without an admitted ``X-Tenant-Id`` (lotus-performance:
401 before any durable job is accepted or Core read is made; 400 above 128 characters after
trimming). This module is the single typed path for that authority: routes admit the header
once, and every tenant-owned downstream request derives its headers from the admitted value.

Authority is per-request only. Pooled shared HTTP clients must never carry tenant default
headers, and no downstream call may derive tenant from a business payload.
"""

from __future__ import annotations

from dataclasses import dataclass

TENANT_ID_HEADER = "X-Tenant-Id"
CORRELATION_ID_HEADER = "X-Correlation-Id"
MAX_TENANT_ID_LENGTH = 128

MISSING_TENANT_AUTHORITY_CODE = "MISSING_TENANT_AUTHORITY"
INVALID_TENANT_AUTHORITY_CODE = "INVALID_TENANT_AUTHORITY"
MISSING_TENANT_AUTHORITY_MESSAGE = (
    "Stateful input requires X-Tenant-Id before any upstream request is made."
)
INVALID_TENANT_AUTHORITY_MESSAGE = (
    f"X-Tenant-Id must not exceed {MAX_TENANT_ID_LENGTH} characters after trimming."
)


class TenantAuthorityError(Exception):
    """Refusal raised before any upstream I/O when admitted tenant authority is unusable."""

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def missing_tenant_authority() -> TenantAuthorityError:
    return TenantAuthorityError(
        status_code=401,
        code=MISSING_TENANT_AUTHORITY_CODE,
        message=MISSING_TENANT_AUTHORITY_MESSAGE,
    )


def invalid_tenant_authority() -> TenantAuthorityError:
    return TenantAuthorityError(
        status_code=400,
        code=INVALID_TENANT_AUTHORITY_CODE,
        message=INVALID_TENANT_AUTHORITY_MESSAGE,
    )


@dataclass(frozen=True, slots=True)
class DownstreamAuthority:
    """Admitted per-request authority for tenant-owned downstream reads.

    Construct through :func:`admit_downstream_authority`; direct construction bypasses
    admission and belongs only in tests that deliberately build an already-admitted value.
    """

    tenant_id: str
    correlation_id: str | None


def admit_downstream_authority(
    *,
    tenant_id: str | None,
    correlation_id: str | None,
) -> DownstreamAuthority:
    """Admit the caller-presented tenant header, refusing before any upstream request.

    Mirrors the enforcing producer contract: a missing or blank tenant is refused as
    unauthenticated authority (401), and a trimmed value above the supported bound is
    refused as malformed (400).
    """
    normalized = tenant_id.strip() if tenant_id is not None else ""
    if not normalized:
        raise missing_tenant_authority()
    if len(normalized) > MAX_TENANT_ID_LENGTH:
        raise invalid_tenant_authority()
    return DownstreamAuthority(tenant_id=normalized, correlation_id=correlation_id)


def required_downstream_authority(
    authority: DownstreamAuthority | None,
) -> DownstreamAuthority:
    """Fail closed when a tenant-owned path is reached without admitted authority."""
    if authority is None:
        raise missing_tenant_authority()
    return authority


def downstream_authority_headers(authority: DownstreamAuthority) -> dict[str, str]:
    """Per-request headers for a tenant-owned downstream request.

    Always built per request from the admitted value; never installed as client defaults.
    """
    headers = {TENANT_ID_HEADER: authority.tenant_id}
    if authority.correlation_id:
        headers[CORRELATION_ID_HEADER] = authority.correlation_id
    return headers


__all__ = [
    "CORRELATION_ID_HEADER",
    "INVALID_TENANT_AUTHORITY_CODE",
    "INVALID_TENANT_AUTHORITY_MESSAGE",
    "MAX_TENANT_ID_LENGTH",
    "MISSING_TENANT_AUTHORITY_CODE",
    "MISSING_TENANT_AUTHORITY_MESSAGE",
    "TENANT_ID_HEADER",
    "DownstreamAuthority",
    "TenantAuthorityError",
    "admit_downstream_authority",
    "downstream_authority_headers",
    "invalid_tenant_authority",
    "missing_tenant_authority",
    "required_downstream_authority",
]
