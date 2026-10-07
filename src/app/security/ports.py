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
    except PrincipalDenied:
        raise
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
