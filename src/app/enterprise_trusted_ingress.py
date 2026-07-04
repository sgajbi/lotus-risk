from __future__ import annotations

import os
from secrets import compare_digest

from app.enterprise_authorization import WRITE_METHODS

TRUSTED_INGRESS_HEADER = "X-Lotus-Trusted-Ingress"
TRUSTED_INGRESS_SECRET_ENV = "ENTERPRISE_TRUSTED_INGRESS_SECRET"  # nosec B105
PROTECTED_OPERATIONAL_PATHS = ("/ops", "/ops/trust-telemetry", "/metrics")


def trusted_ingress_config_issues() -> list[str]:
    if not os.getenv(TRUSTED_INGRESS_SECRET_ENV, "").strip():
        return ["missing_trusted_ingress_secret"]
    return []


def trusted_ingress_required(method: str, path: str) -> bool:
    return method.upper() in WRITE_METHODS or path in PROTECTED_OPERATIONAL_PATHS


def trusted_ingress_authorized(headers: dict[str, str]) -> bool:
    expected = os.getenv(TRUSTED_INGRESS_SECRET_ENV, "").strip()
    if not expected:
        return True
    supplied = _normalized_headers(headers).get(TRUSTED_INGRESS_HEADER.lower(), "")
    return bool(supplied) and compare_digest(supplied, expected)


def _normalized_headers(headers: dict[str, str]) -> dict[str, str]:
    return {str(name).lower(): str(value) for name, value in headers.items()}


__all__ = [
    "PROTECTED_OPERATIONAL_PATHS",
    "TRUSTED_INGRESS_HEADER",
    "TRUSTED_INGRESS_SECRET_ENV",
    "trusted_ingress_authorized",
    "trusted_ingress_config_issues",
    "trusted_ingress_required",
]
