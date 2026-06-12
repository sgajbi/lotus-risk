"""Shared HTTP client profile helpers for downstream upstream adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import httpx

from app.integrations.downstream_request_execution import (
    execute_downstream_request,
    execute_downstream_request_json,
)
from app.integrations.downstream_profile_env import env_float_with_default, env_int_with_default


DEFAULT_TIMEOUT_SECONDS: Final = 10.0
DEFAULT_MAX_CONNECTIONS: Final = 100
DEFAULT_MAX_KEEPALIVE_CONNECTIONS: Final = 20
DEFAULT_KEEPALIVE_EXPIRY_SECONDS: Final = 5.0


@dataclass(frozen=True)
class DownstreamClientProfile:
    timeout_seconds: float
    max_connections: int
    max_keepalive_connections: int
    keepalive_expiry_seconds: float

    def make_client(self) -> httpx.AsyncClient:
        limits = httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
            keepalive_expiry=self.keepalive_expiry_seconds,
        )
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            return httpx.AsyncClient(timeout=timeout, limits=limits)
        except TypeError:
            # Backward-compatible with older/mock AsyncClient implementations that do not
            # expose the `limits` keyword parameter in tests or constrained environments.
            return httpx.AsyncClient(timeout=timeout)


def resolve_downstream_client_profile(
    *,
    env_prefix: str,
    default_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    default_max_connections: int = DEFAULT_MAX_CONNECTIONS,
    default_max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    default_keepalive_expiry_seconds: float = DEFAULT_KEEPALIVE_EXPIRY_SECONDS,
) -> DownstreamClientProfile:
    return DownstreamClientProfile(
        timeout_seconds=env_float_with_default(
            f"{env_prefix}_TIMEOUT_SECONDS", default_timeout_seconds
        ),
        max_connections=env_int_with_default(
            f"{env_prefix}_MAX_CONNECTIONS", default_max_connections
        ),
        max_keepalive_connections=env_int_with_default(
            f"{env_prefix}_MAX_KEEPALIVE_CONNECTIONS", default_max_keepalive_connections
        ),
        keepalive_expiry_seconds=env_float_with_default(
            f"{env_prefix}_KEEPALIVE_EXPIRY_SECONDS", default_keepalive_expiry_seconds
        ),
    )


__all__ = [
    "DownstreamClientProfile",
    "execute_downstream_request",
    "execute_downstream_request_json",
    "resolve_downstream_client_profile",
]
