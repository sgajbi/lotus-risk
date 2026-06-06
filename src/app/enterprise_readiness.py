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
    issues: list[str] = []
    if not enterprise_policy_version().strip():
        issues.append("missing_policy_version")

    rotation_days = _env_int("ENTERPRISE_SECRET_ROTATION_DAYS", 90)
    if rotation_days <= 0 or rotation_days > 90:
        issues.append("secret_rotation_days_out_of_range")

    if (
        _env_enabled("ENTERPRISE_ENFORCE_AUTHZ", "false")
        and not os.getenv("ENTERPRISE_PRIMARY_KEY_ID", "").strip()
    ):
        issues.append("missing_primary_key_id")

    if issues and _env_enabled("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false"):
        raise RuntimeError(f"enterprise_runtime_config_invalid:{','.join(issues)}")
    return issues


def load_feature_flags() -> dict[str, dict[str, dict[str, bool]]]:
    return _load_json_map("ENTERPRISE_FEATURE_FLAGS_JSON")


def load_capability_rules() -> dict[str, str]:
    rules = _load_json_map("ENTERPRISE_CAPABILITY_RULES_JSON")
    return {str(key): str(value) for key, value in rules.items() if isinstance(key, str)}


def _required_capability(method: str, path: str) -> str | None:
    method = method.upper()
    for key, capability in load_capability_rules().items():
        prefix = f"{method} "
        if key.upper().startswith(prefix) and path.startswith(key[len(prefix) :]):
            return capability
    return None


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


def build_enterprise_audit_middleware() -> MiddlewareCallable:
    async def middleware(request: Request, call_next: MiddlewareNext) -> Response:
        payload_limit_response = _payload_limit_response(request)
        if payload_limit_response is not None:
            return payload_limit_response

        authorized, reason = authorize_write_request(
            request.method, request.url.path, dict(request.headers)
        )
        if not authorized:
            return _authorization_denied_response(request, reason=reason)

        response = await call_next(request)
        response.headers["X-Enterprise-Policy-Version"] = enterprise_policy_version()
        _emit_write_audit_event(request, response)
        return response

    return middleware
