from fastapi import HTTPException, Request

from app.contracts.downstream_authority import TENANT_ID_HEADER
from app.security.models import PrincipalDenied, ResolvedPrincipal

CORRELATION_ID_HEADER = "X-Correlation-Id"
ACTOR_ID_HEADER = "X-Actor-Id"


def _request_principal(request: Request) -> ResolvedPrincipal | None:
    principal = getattr(getattr(request, "state", None), "resolved_principal", None)
    if isinstance(principal, ResolvedPrincipal):
        return principal
    app_state = getattr(getattr(request, "app", None), "state", None)
    security = getattr(app_state, "principal_security", None)
    if security is not None and security.posture == "verified":
        raise HTTPException(status_code=503, detail="grant_store_unavailable")
    return None


def request_correlation_id(request: Request) -> str | None:
    correlation = getattr(getattr(request, "state", None), "correlation_id", None)
    return (
        correlation if isinstance(correlation, str) else request.headers.get(CORRELATION_ID_HEADER)
    )


def request_actor_id(request: Request) -> str | None:
    principal = _request_principal(request)
    if principal is not None:
        return principal.credential.subject
    return request.headers.get(ACTOR_ID_HEADER)


def request_tenant_id(request: Request) -> str | None:
    principal = _request_principal(request)
    if principal is not None:
        return principal.credential.tenant_id
    return request.headers.get(TENANT_ID_HEADER)


def require_portfolio_scope(request: Request, portfolio_ids: list[str]) -> None:
    """Resource claims are data: every named portfolio must be entitled, never filtered."""
    principal = _request_principal(request)
    if principal is None:
        return
    try:
        principal.require_portfolios(portfolio_ids)
    except PrincipalDenied as denial:
        request.state.portfolio_scope_denied = True
        raise HTTPException(status_code=denial.status, detail=denial.reason) from None
