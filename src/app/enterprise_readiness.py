import json
import os
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from app.enterprise_audit import emit_audit_event, redact_sensitive
from app.enterprise_authorization import (
    WRITE_METHODS,
    authorize_write_request,
    load_capability_rules,
    missing_supported_write_route_capability_rules,
)
from app.enterprise_policy import enterprise_policy_version
from app.error_response import error_response
from app.integrations.downstream_profile_env import invalid_downstream_runtime_setting_issues

MiddlewareNext = Callable[[Request], Awaitable[Response]]
MiddlewareCallable = Callable[[Request, MiddlewareNext], Awaitable[Response]]

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
    capability_rules = load_capability_rules()
    if not capability_rules:
        issues.append("missing_capability_rules")
    for route_key in missing_supported_write_route_capability_rules(capability_rules):
        issues.append(f"missing_capability_rule:{route_key}")
    if not _env_has_positive_int("ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES"):
        issues.append("missing_or_invalid_max_write_payload_bytes")
    issues.extend(invalid_downstream_runtime_setting_issues())
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


def _content_length(request: Request) -> int:
    try:
        return int(request.headers.get("content-length", "0"))
    except ValueError:
        return 0


def _payload_limit_response(request: Request) -> Response | None:
    max_write_payload_bytes = _env_int("ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES", 1_048_576)
    if request.method not in WRITE_METHODS:
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
    if request.method not in WRITE_METHODS:
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


__all__ = [
    "authorize_write_request",
    "build_enterprise_audit_middleware",
    "emit_audit_event",
    "enterprise_policy_version",
    "load_capability_rules",
    "load_feature_flags",
    "redact_sensitive",
    "validate_enterprise_runtime_config",
]
