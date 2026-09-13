from __future__ import annotations

from typing import Any

import httpx

from app.integrations.upstream_operations import LOTUS_PERFORMANCE_RETURNS_SERIES_OPERATION
from app.upstream_errors import invalid_upstream_payload

RETURNS_SERIES_OPERATION = LOTUS_PERFORMANCE_RETURNS_SERIES_OPERATION


def ensure_dict_payload(
    response: httpx.Response,
    *,
    invalid_message: str,
    operation: str | None = None,
) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=operation or response.request.url.path,
            message=invalid_message,
        )
    return payload


__all__ = [
    "RETURNS_SERIES_OPERATION",
    "ensure_dict_payload",
]
