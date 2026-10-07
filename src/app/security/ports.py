"""Injected identity authority ports; no domain table or hosted grant store."""

from collections.abc import Callable, Mapping
from typing import Protocol

from app.security.models import (
    GrantSet,
    PrincipalDenied,
    SecurityProviderUnavailable,
    VerifiedCredential,
)


def security_provider_call[ProviderResult](
    operation: Callable[[], ProviderResult],
) -> ProviderResult:
    """Provider failure is unavailable authority, never caller-visible exception text."""
    try:
        return operation()
    except Exception as failure:
        raise SecurityProviderUnavailable() from failure


_DECLARED_VERIFIER_DENIALS = {
    "missing_credential": 401,
    "malformed_credential": 401,
    "expired_credential": 401,
    "wrong_audience": 401,
    "wrong_issuer": 401,
    "unknown_key_id": 401,
    "revoked_principal": 401,
    "present_but_unverified": 401,
    "tenant_not_a_member": 403,
    "capability_not_granted": 403,
    "portfolio_outside_scope": 403,
    "delegated_capability_not_held_by_user": 403,
    "grant_store_unavailable": 503,
}


def credential_verifier_call[ProviderResult](
    operation: Callable[[], ProviderResult],
) -> ProviderResult:
    """Only declared caller denials may cross the injected verifier boundary."""
    try:
        return operation()
    except PrincipalDenied as denial:
        if type(denial.reason) is not str or type(denial.status) is not int:
            raise SecurityProviderUnavailable() from None
        expected = _DECLARED_VERIFIER_DENIALS.get(denial.reason)
        if expected is None or denial.status != expected:
            raise SecurityProviderUnavailable() from None
        raise PrincipalDenied(denial.reason, expected) from None
    except Exception as failure:
        raise SecurityProviderUnavailable() from failure


class TrustedKeyProvider(Protocol):
    def jwks(self) -> Mapping[str, object]: ...


class RevocationProvider(Protocol):
    def is_revoked(self, credential_id: str, subject: str) -> bool: ...


class CredentialVerifier(Protocol):
    def verify(self, credential: str) -> VerifiedCredential: ...


class GrantStore(Protocol):
    def tenant_members(self, subject: str, tenant_id: str) -> bool: ...

    def grants_for(self, subject: str, tenant_id: str) -> GrantSet: ...

    def application_grants_for(self, actor: str, tenant_id: str) -> GrantSet: ...
