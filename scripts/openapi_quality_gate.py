from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from app.main import app  # noqa: E402

ALLOWED_METHODS = {"get", "post", "put", "patch", "delete"}


def _has_success_response(operation: dict[str, Any]) -> bool:
    responses = operation.get("responses", {})
    return any(str(code).startswith("2") for code in responses)


def _has_error_response(operation: dict[str, Any]) -> bool:
    responses = operation.get("responses", {})
    return any(
        str(code).startswith("4") or str(code).startswith("5") or str(code) == "default"
        for code in responses
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
