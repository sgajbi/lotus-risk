"""Immutable identity and grant values shared by admission and scope checks."""

from dataclasses import dataclass
from typing import Literal

PrincipalKind = Literal["user", "service", "delegated"]


class PrincipalDenied(Exception):
    """Bounded contract denial, never raw provider or credential content."""

    def __init__(self, reason: str, status: int = 401) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class SecurityProviderUnavailable(Exception):
    """Required trusted identity input could not be established."""


@dataclass(frozen=True)
class VerifiedCredential:
    subject: str
    tenant_id: str
    kind: PrincipalKind
    credential_id: str
    actor: str | None = None


@dataclass(frozen=True)
class GrantSet:
    capabilities: frozenset[str]
    portfolio_ids: frozenset[str]

    def __post_init__(self) -> None:
        for values in (self.capabilities, self.portfolio_ids):
            if not isinstance(values, frozenset) or any(
                not isinstance(value, str) or not value.strip() or value != value.strip()
                for value in values
            ):
                raise SecurityProviderUnavailable("invalid grant set")


@dataclass(frozen=True)
class ResolvedPrincipal:
    credential: VerifiedCredential
    grants: GrantSet

    def require_portfolios(self, portfolio_ids: list[str]) -> None:
        if not set(portfolio_ids).issubset(self.grants.portfolio_ids):
            raise PrincipalDenied("portfolio_outside_scope", 403)
