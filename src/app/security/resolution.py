"""Resolve verified membership, grants, delegated intersections and scope."""

from app.security.configuration import PrincipalProviders
from app.security.models import (
    GrantSet,
    PrincipalDenied,
    ResolvedPrincipal,
    SecurityProviderUnavailable,
    VerifiedCredential,
)
from app.security.ports import GrantStore, security_provider_call


def _require_membership(store: GrantStore, subject: str, tenant: str) -> None:
    membership = security_provider_call(lambda: store.tenant_members(subject, tenant))
    if type(membership) is not bool:
        raise SecurityProviderUnavailable()
    if not membership:
        raise PrincipalDenied("tenant_not_a_member", 403)


def _delegated_grants(
    principal: VerifiedCredential, grants: GrantSet, store: GrantStore, capability: str | None
) -> GrantSet:
    if principal.actor is None:
        raise PrincipalDenied("malformed_credential")
    _require_membership(store, principal.actor, principal.tenant_id)
    actor = principal.actor
    application = security_provider_call(
        lambda: store.application_grants_for(actor, principal.tenant_id)
    )
    if not isinstance(application, GrantSet):
        raise SecurityProviderUnavailable()
    if capability not in grants.capabilities and capability in application.capabilities:
        raise PrincipalDenied("delegated_capability_not_held_by_user", 403)
    return GrantSet(
        capabilities=grants.capabilities & application.capabilities,
        portfolio_ids=grants.portfolio_ids & application.portfolio_ids,
    )


def resolve_principal(
    *,
    credential: str | None,
    capability: str | None,
    providers: PrincipalProviders,
) -> ResolvedPrincipal:
    if not credential:
        raise PrincipalDenied("missing_credential")
    verifier = providers.verifier
    if verifier is None:
        raise PrincipalDenied("grant_store_unavailable", 503)
    try:
        principal = security_provider_call(lambda: verifier.verify(credential))
        if not isinstance(principal, VerifiedCredential):
            raise SecurityProviderUnavailable()
        store = providers.grant_store
        if store is None:
            raise PrincipalDenied("grant_store_unavailable", 503)
        _require_membership(store, principal.subject, principal.tenant_id)
        grants = security_provider_call(
            lambda: store.grants_for(principal.subject, principal.tenant_id)
        )
        if not isinstance(grants, GrantSet):
            raise SecurityProviderUnavailable()
        if principal.kind == "delegated":
            grants = _delegated_grants(principal, grants, store, capability)
        if capability is None or capability not in grants.capabilities:
            raise PrincipalDenied("capability_not_granted", 403)
        return ResolvedPrincipal(credential=principal, grants=grants)
    except SecurityProviderUnavailable:
        raise PrincipalDenied("grant_store_unavailable", 503) from None
