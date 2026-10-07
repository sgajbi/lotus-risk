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
        enforced = os.getenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if enforced:
            for name, reason in (
                ("LOTUS_RISK_PRINCIPAL_POSTURE", "missing_principal_posture"),
                ("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", "missing_deployment_environment"),
            ):
                if name not in os.environ:
                    raise RuntimeError(reason)
        posture = os.getenv("LOTUS_RISK_PRINCIPAL_POSTURE", "header-trust")
        environment = os.getenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", "local")
        if posture not in {"header-trust", "verified"}:
            raise RuntimeError("invalid_principal_posture")
        if environment not in {"local", "dev", "test", "staging", "production"}:
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
