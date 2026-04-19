from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast


REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DECLARATIONS_DIR = REPO_ROOT / "contracts" / "domain-data-products"
PLATFORM_ROOT = REPO_ROOT.parent / "lotus-platform"
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
