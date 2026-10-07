"""Deployment-selected posture and injected runtime providers."""

import os
from dataclasses import dataclass
from typing import Literal, cast

from app.security.ports import CredentialVerifier, GrantStore


@dataclass(frozen=True)
class PrincipalSecurityConfiguration:
    posture: Literal["header-trust", "verified"]
    environment: str

    @classmethod
    def from_environment(cls) -> "PrincipalSecurityConfiguration":
        posture = os.getenv("LOTUS_RISK_PRINCIPAL_POSTURE", "header-trust")
        environment = os.getenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", "local")
        if posture not in {"header-trust", "verified"}:
            raise RuntimeError("invalid_principal_posture")
        if not environment.strip() or environment != environment.strip():
            raise RuntimeError("invalid_deployment_environment")
        if posture == "header-trust" and environment not in {"local", "dev"}:
            raise RuntimeError("header_trust_requires_local_or_dev")
        return cls(
            posture=cast(Literal["header-trust", "verified"], posture), environment=environment
        )


@dataclass(frozen=True)
class PrincipalProviders:
    verifier: CredentialVerifier | None = None
    grant_store: GrantStore | None = None
