from __future__ import annotations

import json
import os
from typing import Any

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

ENTERPRISE_AUTHORIZATION_REQUIRED_HEADERS = (
    "X-Actor-Id",
    "X-Tenant-Id",
    "X-Role",
    "X-Correlation-Id",
)
ENTERPRISE_SERVICE_IDENTITY_HEADERS = ("Authorization", "X-Service-Identity")
ENTERPRISE_CAPABILITIES_HEADER = "X-Capabilities"
SUPPORTED_WRITE_ROUTES = (
    ("POST", "/analytics/risk/calculate"),
    ("POST", "/analytics/risk/concentration"),
    ("POST", "/analytics/risk/drawdown"),
    ("POST", "/analytics/risk/historical-attribution"),
    ("POST", "/analytics/risk/mandate-health-context"),
    ("POST", "/analytics/risk/regime-scenario-pack/evaluate"),
    ("POST", "/analytics/risk/risk-event-cohorts/evaluate"),
    ("POST", "/analytics/risk/rolling-metrics"),
)

_REQUIRED_HEADERS = {header.lower() for header in ENTERPRISE_AUTHORIZATION_REQUIRED_HEADERS}


def _env_enabled(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _load_json_map(name: str) -> dict[str, Any]:
    raw = os.getenv(name, "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_capability_rules() -> dict[str, str]:
    rules = _load_json_map("ENTERPRISE_CAPABILITY_RULES_JSON")
    return {key: value for key, value in rules.items() if _valid_capability_rule(key, value)}


def _valid_capability_rule(key: Any, value: Any) -> bool:
    if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
        return False
    if key != key.strip() or value != value.strip():
        return False
    method, separator, path = key.partition(" ")
    return bool(separator and method.upper() in WRITE_METHODS and path.startswith("/"))


def _path_matches_rule(path: str, rule_path: str) -> bool:
    normalized_rule_path = rule_path.rstrip("/") or "/"
    return path == normalized_rule_path or path.startswith(f"{normalized_rule_path}/")


def _required_capability_from_rules(
    rules: dict[str, str],
    *,
    method: str,
    path: str,
) -> str | None:
    method = method.upper()
    matching_rules: list[tuple[int, str]] = []
    for key, capability in rules.items():
        prefix = f"{method} "
        rule_path = key[len(prefix) :]
        if key.upper().startswith(prefix) and _path_matches_rule(path, rule_path):
            matching_rules.append((len(rule_path.rstrip("/")), capability))
    if not matching_rules:
        return None
    return max(matching_rules, key=lambda item: item[0])[1]


def _required_capability(method: str, path: str) -> str | None:
    return _required_capability_from_rules(load_capability_rules(), method=method, path=path)


def missing_supported_write_route_capability_rules(
    rules: dict[str, str] | None = None,
) -> list[str]:
    capability_rules = load_capability_rules() if rules is None else rules
    return [
        f"{method} {path}"
        for method, path in SUPPORTED_WRITE_ROUTES
        if _required_capability_from_rules(capability_rules, method=method, path=path) is None
    ]


def _authorization_enforced(method: str) -> bool:
    return method.upper() in WRITE_METHODS and _env_enabled("ENTERPRISE_ENFORCE_AUTHZ", "false")


def _normalized_headers(headers: dict[str, str]) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in headers.items()}


def _missing_required_headers(normalized_headers: dict[str, str]) -> list[str]:
    return sorted(header for header in _REQUIRED_HEADERS if not normalized_headers.get(header))


def _has_service_identity(normalized_headers: dict[str, str]) -> bool:
    return bool(
        normalized_headers.get("x-service-identity") or normalized_headers.get("authorization")
    )


def _capability_set(normalized_headers: dict[str, str]) -> set[str]:
    return {
        part.strip()
        for part in normalized_headers.get("x-capabilities", "").split(",")
        if part.strip()
    }


def _missing_capability_reason(
    method: str,
    path: str,
    normalized_headers: dict[str, str],
) -> str | None:
    required_capability = _required_capability(method, path)
    if required_capability is None:
        return "missing_capability_rule"
    if required_capability and required_capability not in _capability_set(normalized_headers):
        return f"missing_capability:{required_capability}"
    return None


def authorize_write_request(
    method: str, path: str, headers: dict[str, str]
) -> tuple[bool, str | None]:
    if not _authorization_enforced(method):
        return True, None

    normalized = _normalized_headers(headers)
    missing = _missing_required_headers(normalized)
    if missing:
        return False, f"missing_headers:{','.join(missing)}"

    if not _has_service_identity(normalized):
        return False, "missing_service_identity"

    missing_capability = _missing_capability_reason(method, path, normalized)
    if missing_capability:
        return False, missing_capability

    return True, None


__all__ = [
    "ENTERPRISE_AUTHORIZATION_REQUIRED_HEADERS",
    "ENTERPRISE_CAPABILITIES_HEADER",
    "ENTERPRISE_SERVICE_IDENTITY_HEADERS",
    "SUPPORTED_WRITE_ROUTES",
    "WRITE_METHODS",
    "authorize_write_request",
    "load_capability_rules",
    "missing_supported_write_route_capability_rules",
]
