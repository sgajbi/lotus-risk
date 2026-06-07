import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from app.error_response import error_response

logger = logging.getLogger("enterprise_readiness")
MiddlewareNext = Callable[[Request], Awaitable[Response]]
MiddlewareCallable = Callable[[Request, MiddlewareNext], Awaitable[Response]]

_SERVICE_NAME = "lotus-risk"
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_REQUIRED_HEADERS = {"x-actor-id", "x-tenant-id", "x-role", "x-correlation-id"}
_REDACT_FIELDS = {
    "password",
    "secret",
    "token",
    "authorization",
    "ssn",
    "account_number",
    "client_email",
}
_SECURITY_RESPONSE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def _env_enabled(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _load_json_map(name: str) -> dict[str, Any]:
    raw = os.getenv(name, "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def enterprise_policy_version() -> str:
    return os.getenv("ENTERPRISE_POLICY_VERSION", "1.0.0")


def validate_enterprise_runtime_config() -> list[str]:
    issues = _base_runtime_config_issues()
    runtime_config_enforced = _env_enabled("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false")
    if runtime_config_enforced:
        issues.extend(_enterprise_bank_config_issues())
    issues = list(dict.fromkeys(issues))
    if issues and runtime_config_enforced:
        raise RuntimeError(f"enterprise_runtime_config_invalid:{','.join(issues)}")
    return issues


def _base_runtime_config_issues() -> list[str]:
    issues: list[str] = []
    if not enterprise_policy_version().strip():
        issues.append("missing_policy_version")

    rotation_days = _env_int("ENTERPRISE_SECRET_ROTATION_DAYS", 90)
    if rotation_days <= 0 or rotation_days > 90:
        issues.append("secret_rotation_days_out_of_range")

    if _env_enabled("ENTERPRISE_ENFORCE_AUTHZ", "false") and not _env_has_value(
        "ENTERPRISE_PRIMARY_KEY_ID"
    ):
        issues.append("missing_primary_key_id")
    return issues


def _enterprise_bank_config_issues() -> list[str]:
    issues: list[str] = []
    if not _env_enabled("ENTERPRISE_ENFORCE_AUTHZ", "false"):
        issues.append("authorization_not_enforced")
    for env_name, issue in (
        ("ENTERPRISE_POLICY_VERSION", "missing_policy_version"),
        ("ENTERPRISE_PRIMARY_KEY_ID", "missing_primary_key_id"),
        ("ENTERPRISE_SECRET_ROTATION_DAYS", "missing_secret_rotation_days"),
        ("LOTUS_CORE_BASE_URL", "missing_lotus_core_base_url"),
        ("LOTUS_PERFORMANCE_BASE_URL", "missing_lotus_performance_base_url"),
    ):
        if not _env_has_value(env_name):
            issues.append(issue)
    if not load_capability_rules():
        issues.append("missing_capability_rules")
    if not _env_has_positive_int("ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES"):
        issues.append("missing_or_invalid_max_write_payload_bytes")
    return issues


def _env_has_value(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _env_has_positive_int(name: str) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return False
    try:
        return int(raw_value) > 0
    except ValueError:
        return False


def load_feature_flags() -> dict[str, dict[str, dict[str, bool]]]:
    return _load_json_map("ENTERPRISE_FEATURE_FLAGS_JSON")


def load_capability_rules() -> dict[str, str]:
    rules = _load_json_map("ENTERPRISE_CAPABILITY_RULES_JSON")
    return {key: value for key, value in rules.items() if _valid_capability_rule(key, value)}


def _valid_capability_rule(key: Any, value: Any) -> bool:
    if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
        return False
    if key != key.strip() or value != value.strip():
        return False
    method, separator, path = key.partition(" ")
    return bool(separator and method.upper() in _WRITE_METHODS and path.startswith("/"))


def _required_capability(method: str, path: str) -> str | None:
    method = method.upper()
    matching_rules: list[tuple[int, str]] = []
    for key, capability in load_capability_rules().items():
        prefix = f"{method} "
        rule_path = key[len(prefix) :]
        if key.upper().startswith(prefix) and _path_matches_rule(path, rule_path):
            matching_rules.append((len(rule_path.rstrip("/")), capability))
    if not matching_rules:
        return None
    return max(matching_rules, key=lambda item: item[0])[1]


def _path_matches_rule(path: str, rule_path: str) -> bool:
    normalized_rule_path = rule_path.rstrip("/") or "/"
    return path == normalized_rule_path or path.startswith(f"{normalized_rule_path}/")


def _authorization_enforced(method: str) -> bool:
    return method.upper() in _WRITE_METHODS and _env_enabled("ENTERPRISE_ENFORCE_AUTHZ", "false")


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


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in _REDACT_FIELDS:
                out[key] = "***REDACTED***"
            else:
                out[key] = redact_sensitive(item)
        return out
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def emit_audit_event(
    *,
    action: str,
    actor_id: str,
    tenant_id: str,
    role: str,
    correlation_id: str | None,
    metadata: dict[str, Any],
) -> None:
    logger.info(
        "enterprise_audit_event",
        extra={
            "audit": {
                "service": _SERVICE_NAME,
                "action": action,
                "actor_id": actor_id,
                "tenant_id": tenant_id,
                "role": role,
                "correlation_id": correlation_id or "",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "policy_version": enterprise_policy_version(),
                "metadata": redact_sensitive(metadata),
            }
        },
    )


def _content_length(request: Request) -> int:
    try:
        return int(request.headers.get("content-length", "0"))
    except ValueError:
        return 0


def _payload_limit_response(request: Request) -> Response | None:
    max_write_payload_bytes = _env_int("ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES", 1_048_576)
    if request.method not in _WRITE_METHODS:
        return None
    if _content_length(request) <= max_write_payload_bytes:
        return None
    return error_response(
        request,
        status_code=413,
        code="PAYLOAD_TOO_LARGE",
        message="payload_too_large",
    )


def _authorization_denied_response(
    request: Request,
    *,
    reason: str | None,
) -> Response:
    emit_audit_event(
        action=f"DENY {request.method} {request.url.path}",
        actor_id=request.headers.get("X-Actor-Id", "unknown"),
        tenant_id=request.headers.get("X-Tenant-Id", "default"),
        role=request.headers.get("X-Role", "unknown"),
        correlation_id=request.headers.get("X-Correlation-Id"),
        metadata={"reason": reason},
    )
    return error_response(
        request,
        status_code=403,
        code="AUTHORIZATION_DENIED",
        message="authorization_policy_denied",
        details={"reason": reason},
    )


def _emit_write_audit_event(request: Request, response: Response) -> None:
    if request.method not in _WRITE_METHODS:
        return
    emit_audit_event(
        action=f"{request.method} {request.url.path}",
        actor_id=request.headers.get("X-Actor-Id", "unknown"),
        tenant_id=request.headers.get("X-Tenant-Id", "default"),
        role=request.headers.get("X-Role", "unknown"),
        correlation_id=request.headers.get("X-Correlation-Id"),
        metadata={"status_code": response.status_code},
    )


def _apply_enterprise_response_headers(response: Response) -> Response:
    response.headers["X-Enterprise-Policy-Version"] = enterprise_policy_version()
    for name, value in _SECURITY_RESPONSE_HEADERS.items():
        response.headers[name] = value
    return response


def build_enterprise_audit_middleware() -> MiddlewareCallable:
    async def middleware(request: Request, call_next: MiddlewareNext) -> Response:
        payload_limit_response = _payload_limit_response(request)
        if payload_limit_response is not None:
            return _apply_enterprise_response_headers(payload_limit_response)

        authorized, reason = authorize_write_request(
            request.method, request.url.path, dict(request.headers)
        )
        if not authorized:
            return _apply_enterprise_response_headers(
                _authorization_denied_response(request, reason=reason)
            )

        response = await call_next(request)
        _emit_write_audit_event(request, response)
        return _apply_enterprise_response_headers(response)

    return middleware
