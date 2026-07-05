from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
SRC_STR = str(SRC)
while SRC_STR in sys.path:
    sys.path.remove(SRC_STR)
sys.path.insert(0, SRC_STR)
LOCAL_DECLARATIONS_DIR = REPO_ROOT / "contracts" / "domain-data-products"


def _resolve_platform_root() -> Path:
    configured_root = os.environ.get("LOTUS_PLATFORM_ROOT")
    candidates = []
    if configured_root:
        candidates.append(Path(configured_root))
    candidates.extend(
        [
            REPO_ROOT.parent / "lotus-platform",
            REPO_ROOT / ".lotus-platform",
            REPO_ROOT / "lotus-platform",
        ]
    )

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "platform-contracts").exists():
            return resolved

    return candidates[0].expanduser().resolve()


PLATFORM_ROOT = _resolve_platform_root()
PLATFORM_DECLARATIONS_DIR = PLATFORM_ROOT / "platform-contracts" / "domain-data-products"
PLATFORM_VOCABULARY_DIR = PLATFORM_ROOT / "platform-contracts" / "domain-vocabulary"
PLATFORM_VALIDATOR_PATH = PLATFORM_DECLARATIONS_DIR / "validate_domain_data_product_contracts.py"
LOCAL_PRODUCER_PATH = LOCAL_DECLARATIONS_DIR / "lotus-risk-products.v1.json"
LOCAL_CONSUMER_PATH = LOCAL_DECLARATIONS_DIR / "lotus-risk-consumers.v1.json"
TRANSITIONAL_PLATFORM_MIRRORS = (
    ("producer", LOCAL_PRODUCER_PATH, PLATFORM_DECLARATIONS_DIR / "lotus-risk-products.v1.json"),
    ("consumer", LOCAL_CONSUMER_PATH, PLATFORM_DECLARATIONS_DIR / "lotus-risk-consumers.v1.json"),
)
SUPPLEMENTAL_PLATFORM_PRODUCERS = (
    PLATFORM_DECLARATIONS_DIR / "lotus-core-products.v1.json",
    PLATFORM_DECLARATIONS_DIR / "lotus-performance-products.v1.json",
)
TRUST_METADATA_RESPONSE_PATHS: dict[str, tuple[str, ...]] = {
    "product_name": ("metadata.product_name", "product_name"),
    "product_version": ("metadata.product_version", "product_version"),
    "as_of_date": ("scope.as_of_date", "metadata.as_of_date", "as_of_date"),
    "lineage_version": ("metadata.lineage_version", "lineage_version"),
    "request_fingerprint": ("metadata.request_fingerprint", "request_fingerprint"),
    "source_services": ("metadata.source_services", "source_services"),
    "upstream_request_fingerprints": (
        "metadata.upstream_request_fingerprints",
        "upstream_request_fingerprints",
    ),
    "benchmark_context": ("metadata.benchmark_context", "benchmark_context"),
    "risk_free_context": ("metadata.risk_free_context", "risk_free_context"),
    "correlation_id": ("metadata.correlation_id", "correlation_id"),
    "coverage_ratio": (
        "metadata.coverage_ratio",
        "issuer_concentration.coverage_ratio_current",
    ),
    "coverage_status": (
        "metadata.coverage_status",
        "issuer_concentration.coverage_status",
    ),
}


def platform_validation_dependencies_available() -> bool:
    required_paths = (
        PLATFORM_VALIDATOR_PATH,
        PLATFORM_DECLARATIONS_DIR / "lotus-risk-products.v1.json",
        PLATFORM_DECLARATIONS_DIR / "lotus-risk-consumers.v1.json",
        PLATFORM_VOCABULARY_DIR / "domain-data-product-semantics.v1.json",
        PLATFORM_VOCABULARY_DIR / "domain-data-product-trust-metadata.v1.json",
        *SUPPLEMENTAL_PLATFORM_PRODUCERS,
    )
    return all(path.exists() for path in required_paths)


def _load_platform_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "lotus_platform_domain_data_products_validator", PLATFORM_VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load platform validator from {PLATFORM_VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _append_issue(issues: list[str], path: Path, message: str) -> None:
    issues.append(f"{path}: {message}")


def _response_schema_for_route(
    openapi_payload: dict[str, Any], route: str
) -> dict[str, Any] | None:
    route_payload = openapi_payload.get("paths", {}).get(route)
    if not isinstance(route_payload, dict):
        return None
    post_payload = route_payload.get("post")
    if not isinstance(post_payload, dict):
        return None
    schema = (
        post_payload.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    return schema if isinstance(schema, dict) else None


def _resolve_schema_ref(openapi_payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema
    target: Any = openapi_payload
    for segment in ref.removeprefix("#/").split("/"):
        if not isinstance(target, dict):
            return schema
        target = target.get(segment)
    return target if isinstance(target, dict) else schema


def _schema_has_path(
    openapi_payload: dict[str, Any],
    schema: dict[str, Any],
    path: str,
) -> bool:
    return _schema_has_path_tokens(openapi_payload, schema, path.split("."))


def _schema_has_path_tokens(
    openapi_payload: dict[str, Any],
    schema: dict[str, Any],
    tokens: list[str],
) -> bool:
    schema = _resolve_schema_ref(openapi_payload, schema)
    for union_key in ("allOf", "anyOf", "oneOf"):
        union_schemas = schema.get(union_key)
        if isinstance(union_schemas, list) and any(
            isinstance(candidate, dict)
            and _schema_has_path_tokens(openapi_payload, candidate, tokens)
            for candidate in union_schemas
        ):
            return True

    if not tokens:
        return True

    token = tokens[0]
    if token == "*":
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return _schema_has_path_tokens(openapi_payload, additional, tokens[1:])
        items = schema.get("items")
        if isinstance(items, dict):
            return _schema_has_path_tokens(openapi_payload, items, tokens[1:])
        return False

    properties = schema.get("properties")
    if isinstance(properties, dict):
        child = properties.get(token)
        if isinstance(child, dict):
            return _schema_has_path_tokens(openapi_payload, child, tokens[1:])

    return False


def validate_declared_route_response_metadata(
    *,
    producer_payload: dict[str, Any],
    openapi_payload: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    products = producer_payload.get("products")
    if not isinstance(products, list):
        return ["domain data product declaration: products must be a list"]

    for product in products:
        if not isinstance(product, dict):
            continue
        product_name = str(product.get("product_name", "<unknown>"))
        required_metadata = product.get("required_trust_metadata")
        routes = product.get("current_routes")
        if not isinstance(required_metadata, list) or not isinstance(routes, list):
            continue
        for route in routes:
            if not isinstance(route, str):
                continue
            route_schema = _response_schema_for_route(openapi_payload, route)
            if route_schema is None:
                issues.append(f"{product_name}: route {route} has no JSON 200 response schema")
                continue
            for field in required_metadata:
                if not isinstance(field, str):
                    continue
                candidate_paths = TRUST_METADATA_RESPONSE_PATHS.get(field)
                if not candidate_paths:
                    issues.append(
                        f"{product_name}: required trust metadata {field!r} has no governed "
                        "response-schema mapping"
                    )
                    continue
                if not any(
                    _schema_has_path(openapi_payload, route_schema, candidate_path)
                    for candidate_path in candidate_paths
                ):
                    issues.append(
                        f"{product_name}: route {route} omits required trust metadata "
                        f"{field!r}; expected one of {list(candidate_paths)}"
                    )
    return issues


def _load_registry_keys(
    semantics_payload: dict[str, Any],
    trust_payload: dict[str, Any],
) -> dict[str, set[str]]:
    return {
        "identifier_keys": {
            entry.get("key", "")
            for entry in semantics_payload.get("identifiers", [])
            if isinstance(entry, dict)
        },
        "temporal_keys": {
            entry.get("key", "")
            for entry in semantics_payload.get("temporal_semantics", [])
            if isinstance(entry, dict)
        },
        "freshness_classes": {
            entry.get("key", "")
            for entry in semantics_payload.get("trust_vocabularies", {}).get(
                "freshness_classes", []
            )
            if isinstance(entry, dict)
        },
        "completeness_statuses": {
            entry.get("key", "")
            for entry in semantics_payload.get("trust_vocabularies", {}).get(
                "completeness_statuses", []
            )
            if isinstance(entry, dict)
        },
        "trust_metadata_keys": {
            entry.get("key", "")
            for entry in trust_payload.get("trust_metadata_fields", [])
            if isinstance(entry, dict)
        },
        "evidence_access_classes": {
            entry.get("key", "")
            for entry in trust_payload.get("evidence_access_classes", [])
            if isinstance(entry, dict)
        },
        "lineage_bundle_class_keys": {
            entry.get("key", "")
            for entry in trust_payload.get("lineage_bundle_classes", [])
            if isinstance(entry, dict)
        },
    }


def validate_repo_native_contracts() -> list[str]:
    validator = _load_platform_validator()
    issues: list[str] = []

    semantics_path = PLATFORM_VOCABULARY_DIR / "domain-data-product-semantics.v1.json"
    trust_path = PLATFORM_VOCABULARY_DIR / "domain-data-product-trust-metadata.v1.json"
    semantics_payload = _load_json(semantics_path)
    trust_payload = _load_json(trust_path)

    issues.extend(validator.validate_semantics_registry(semantics_path, semantics_payload))
    issues.extend(validator.validate_trust_metadata_registry(trust_path, trust_payload))
    registry_keys = _load_registry_keys(semantics_payload, trust_payload)

    local_producer_payload = _load_json(LOCAL_PRODUCER_PATH)
    local_consumer_payload = _load_json(LOCAL_CONSUMER_PATH)

    issues.extend(
        validator.validate_producer_contract(
            LOCAL_PRODUCER_PATH,
            local_producer_payload,
            identifier_keys=registry_keys["identifier_keys"],
            temporal_keys=registry_keys["temporal_keys"],
            freshness_classes=registry_keys["freshness_classes"],
            completeness_statuses=registry_keys["completeness_statuses"],
            trust_metadata_keys=registry_keys["trust_metadata_keys"],
            evidence_access_classes=registry_keys["evidence_access_classes"],
            lineage_bundle_class_keys=registry_keys["lineage_bundle_class_keys"],
        )
    )
    issues.extend(
        validator.validate_consumer_contract_with_context(
            LOCAL_CONSUMER_PATH,
            local_consumer_payload,
            trust_metadata_keys=registry_keys["trust_metadata_keys"],
        )
    )

    producer_payloads: list[tuple[Path, dict[str, Any]]] = [
        (LOCAL_PRODUCER_PATH, local_producer_payload)
    ]
    for supplemental_path in SUPPLEMENTAL_PLATFORM_PRODUCERS:
        producer_payloads.append((supplemental_path, _load_json(supplemental_path)))
    issues.extend(
        validator.validate_cross_references(
            producer_payloads, [(LOCAL_CONSUMER_PATH, local_consumer_payload)]
        )
    )

    for mirror_kind, local_path, platform_path in TRANSITIONAL_PLATFORM_MIRRORS:
        local_payload = _load_json(local_path)
        platform_payload = _load_json(platform_path)
        if local_payload != platform_payload:
            _append_issue(
                issues,
                local_path,
                f"repo-native {mirror_kind} declaration drifted from transitional platform mirror {platform_path}",
            )

    from app.main import app

    issues.extend(
        validate_declared_route_response_metadata(
            producer_payload=local_producer_payload,
            openapi_payload=app.openapi(),
        )
    )

    return issues


def main() -> int:
    issues = validate_repo_native_contracts()
    if issues:
        for issue in issues:
            print(issue)
        return 1

    print(
        "Validated lotus-risk repo-native domain data product declarations against platform registries, "
        "cross-references, and transitional mirrors."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
