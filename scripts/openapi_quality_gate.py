from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = str(PROJECT_ROOT / "scripts")
if SCRIPT_PATH not in sys.path:
    sys.path.insert(0, SCRIPT_PATH)

try:
    from scripts._repo_imports import force_repo_src_first
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from _repo_imports import force_repo_src_first  # type: ignore[import-not-found,no-redef]

force_repo_src_first(PROJECT_ROOT)

from app.enterprise_authorization import SUPPORTED_WRITE_ROUTES
from app.main import app

ALLOWED_METHODS = {"get", "post", "put", "patch", "delete"}
JSON_MUTATION_METHODS = {"post", "put", "patch"}
SUPPORTED_WRITE_ROUTE_KEYS = {(method.lower(), path) for method, path in SUPPORTED_WRITE_ROUTES}


def _has_success_response(operation: dict[str, Any]) -> bool:
    responses = operation.get("responses", {})
    return any(str(code).startswith("2") for code in responses)


def _has_error_response(operation: dict[str, Any]) -> bool:
    responses = operation.get("responses", {})
    return any(
        str(code).startswith("4") or str(code).startswith("5") or str(code) == "default"
        for code in responses
    )


def _has_json_request_examples(operation: dict[str, Any]) -> bool:
    json_content = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    return bool(json_content.get("examples") or json_content.get("example"))


def _has_enterprise_authorization_extension(operation: dict[str, Any]) -> bool:
    extension = operation.get("x-lotus-enterprise-authorization")
    if not isinstance(extension, dict):
        return False
    return all(
        extension.get(field)
        for field in (
            "required_context_headers",
            "service_identity_headers",
            "trusted_ingress_header",
            "capabilities_header",
            "capability_rules_env",
            "denial_code",
            "denial_reason",
        )
    )


def _is_ref_only(prop_schema: dict[str, Any]) -> bool:
    return set(prop_schema.keys()) == {"$ref"}


def evaluate_schema(schema: dict[str, Any], *, service_name: str) -> list[str]:
    errors: list[str] = []
    missing_docs: list[tuple[str, str, str]] = []
    missing_fields: list[tuple[str, str, str]] = []
    operation_ids: list[str] = []

    for path, methods in schema.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in ALLOWED_METHODS:
                continue
            if not isinstance(operation, dict):
                continue

            method_upper = method.upper()
            operation_id = operation.get("operationId")
            if operation_id:
                operation_ids.append(str(operation_id))
            else:
                missing_docs.append((method_upper, path, "operationId"))

            if not operation.get("summary"):
                missing_docs.append((method_upper, path, "summary"))
            if not operation.get("description"):
                missing_docs.append((method_upper, path, "description"))
            if not operation.get("tags"):
                missing_docs.append((method_upper, path, "tags"))

            if not operation.get("responses"):
                missing_docs.append((method_upper, path, "responses"))
            else:
                if not _has_success_response(operation):
                    missing_docs.append((method_upper, path, "2xx response"))
                if not _has_error_response(operation):
                    missing_docs.append((method_upper, path, "error response (4xx/5xx/default)"))
            if (
                method.lower() in JSON_MUTATION_METHODS
                and operation.get("requestBody")
                and not _has_json_request_examples(operation)
            ):
                missing_docs.append((method_upper, path, "JSON request example"))
            if (method.lower(), path) in SUPPORTED_WRITE_ROUTE_KEYS:
                if not _has_enterprise_authorization_extension(operation):
                    missing_docs.append(
                        (
                            method_upper,
                            path,
                            "enterprise authorization caller-context extension",
                        )
                    )
                if "403" not in {
                    str(status_code) for status_code in operation.get("responses", {})
                }:
                    missing_docs.append((method_upper, path, "403 authorization response"))

    schemas = schema.get("components", {}).get("schemas", {})
    if isinstance(schemas, dict):
        for model_name, model_schema in schemas.items():
            if not isinstance(model_schema, dict):
                continue
            properties = model_schema.get("properties", {})
            if not isinstance(properties, dict):
                continue
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    continue
                if _is_ref_only(prop_schema):
                    continue
                if not prop_schema.get("description"):
                    missing_fields.append((str(model_name), str(prop_name), "description"))
                if "example" not in prop_schema and "examples" not in prop_schema:
                    missing_fields.append((str(model_name), str(prop_name), "example"))

    if missing_docs:
        errors.append(
            f"OpenAPI quality gate ({service_name}): missing endpoint documentation/response contract"
        )
        errors.extend(
            f"  - {method} {path}: missing {field_name}"
            for method, path, field_name in missing_docs
        )

    if missing_fields:
        errors.append(f"OpenAPI quality gate ({service_name}): missing schema field metadata")
        errors.extend(
            f"  - {model}.{field}: missing {field_name}"
            for model, field, field_name in missing_fields
        )

    duplicate_operation_ids = sorted(
        [op_id for op_id, count in Counter(operation_ids).items() if count > 1]
    )
    if duplicate_operation_ids:
        errors.append(f"OpenAPI quality gate ({service_name}): duplicate operationId values")
        errors.extend(f"  - {op_id}" for op_id in duplicate_operation_ids)

    return errors


def main() -> int:
    schema = app.openapi()
    if "paths" not in schema or not schema["paths"]:
        print("OpenAPI quality gate (lotus-risk): no paths defined")
        return 1

    errors = evaluate_schema(schema, service_name="lotus-risk")
    if errors:
        print("\n".join(errors))
        return 1

    print("OpenAPI quality gate passed for lotus-risk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
