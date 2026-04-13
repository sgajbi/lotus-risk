from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def fingerprint_payload(payload: Any) -> str:
    normalized = _to_jsonable(payload)
    serialized = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def fingerprint_model(model: BaseModel) -> str:
    return fingerprint_payload(model.model_dump(mode="json", exclude_none=False))


def upstream_request_fingerprint(
    *,
    service: str,
    operation: str,
    payload: Any,
) -> dict[str, str]:
    return {f"{service}:{operation}": fingerprint_payload(payload)}


def ordered_source_services(*services: str) -> list[str]:
    ordered: list[str] = []
    for service in ("lotus-risk", *services):
        if service not in ordered:
            ordered.append(service)
    return ordered


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    return value
