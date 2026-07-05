from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]
LOCAL_TELEMETRY_DIR = ROOT / "contracts" / "trust-telemetry"
LOCAL_PRODUCT_DECLARATION_PATH = (
    ROOT / "contracts" / "domain-data-products" / "lotus-risk-products.v1.json"
)
LOCAL_TELEMETRY_COVERAGE_PATH = (
    ROOT / "contracts" / "trust-telemetry-coverage" / "lotus-risk-trust-telemetry-coverage.v1.json"
)
CERTIFIED_STATIC_SNAPSHOT = "certified_static_snapshot"
PENDING_STATIC_SNAPSHOT = "pending_static_snapshot"
SUPPORTED_COVERAGE_STATUSES = {CERTIFIED_STATIC_SNAPSHOT, PENDING_STATIC_SNAPSHOT}


def _resolve_platform_root() -> Path:
    configured_root = os.environ.get("LOTUS_PLATFORM_ROOT")
    candidates = []
    if configured_root:
        candidates.append(Path(configured_root))
    candidates.extend(
        [
            ROOT.parent / "lotus-platform",
            ROOT / ".lotus-platform",
            ROOT / "lotus-platform",
        ]
    )

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "platform-contracts").exists():
            return resolved

    return candidates[0].expanduser().resolve()


PLATFORM_ROOT = _resolve_platform_root()
PLATFORM_AUTOMATION_DIR = PLATFORM_ROOT / "automation"
PLATFORM_VALIDATOR_PATH = PLATFORM_AUTOMATION_DIR / "validate_trust_telemetry.py"
PLATFORM_CATALOG_PATH = PLATFORM_ROOT / "generated" / "domain-product-catalog.json"
PLATFORM_VOCABULARY_DIR = PLATFORM_ROOT / "platform-contracts" / "domain-vocabulary"
PLATFORM_TRUST_METADATA_REGISTRY_PATH = (
    PLATFORM_VOCABULARY_DIR / "domain-data-product-trust-metadata.v1.json"
)
PLATFORM_SEMANTICS_REGISTRY_PATH = PLATFORM_VOCABULARY_DIR / "domain-data-product-semantics.v1.json"


def _load_platform_validator() -> ModuleType:
    if not PLATFORM_VALIDATOR_PATH.exists():
        raise FileNotFoundError(
            f"Platform trust telemetry validator not found at {PLATFORM_VALIDATOR_PATH}. "
            "Ensure lotus-platform is available as a sibling checkout, under this repository, "
            "or through LOTUS_PLATFORM_ROOT."
        )

    automation_path = str(PLATFORM_AUTOMATION_DIR)
    inserted = automation_path not in sys.path
    if inserted:
        sys.path.insert(0, automation_path)
    try:
        spec = importlib.util.spec_from_file_location(
            "lotus_platform_trust_telemetry_validator",
            PLATFORM_VALIDATOR_PATH,
        )
        if spec is None or spec.loader is None:
            raise ImportError(
                f"Unable to load platform trust telemetry validator from {PLATFORM_VALIDATOR_PATH}"
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            sys.path.remove(automation_path)


def platform_validation_dependencies_available() -> bool:
    return all(
        path.exists()
        for path in (
            PLATFORM_VALIDATOR_PATH,
            PLATFORM_CATALOG_PATH,
            PLATFORM_TRUST_METADATA_REGISTRY_PATH,
            PLATFORM_SEMANTICS_REGISTRY_PATH,
        )
    )


def validate_repo_native_trust_telemetry(
    source_directory: Path = LOCAL_TELEMETRY_DIR,
    product_declaration_path: Path = LOCAL_PRODUCT_DECLARATION_PATH,
    coverage_path: Path = LOCAL_TELEMETRY_COVERAGE_PATH,
) -> list[str]:
    source_directory = source_directory.resolve()
    if not source_directory.exists():
        return [f"{source_directory}: repo-native trust telemetry directory does not exist"]
    if not list(source_directory.glob("*.telemetry.v1.json")):
        return [f"{source_directory}: no repo-native trust telemetry snapshot files were found"]

    validator = _load_platform_validator()
    issues = cast(
        list[str],
        validator.validate_trust_telemetry_path(
            source_directory,
            catalog_path=PLATFORM_CATALOG_PATH,
            trust_metadata_registry_path=PLATFORM_TRUST_METADATA_REGISTRY_PATH,
            semantics_registry_path=PLATFORM_SEMANTICS_REGISTRY_PATH,
        ),
    )
    issues.extend(
        validate_trust_telemetry_coverage(
            source_directory=source_directory,
            product_declaration_path=product_declaration_path,
            coverage_path=coverage_path,
        )
    )
    return issues


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _active_product_keys(product_declaration_path: Path) -> set[tuple[str, str]]:
    payload = _load_json(product_declaration_path)
    return {
        (str(product["product_name"]), str(product["product_version"]))
        for product in payload.get("products", [])
        if isinstance(product, dict) and product.get("lifecycle_status") == "active"
    }


def _snapshot_product_keys(source_directory: Path) -> set[tuple[str, str]]:
    product_keys: set[tuple[str, str]] = set()
    for snapshot_path in source_directory.glob("*.telemetry.v1.json"):
        payload = _load_json(snapshot_path)
        product_keys.add((str(payload.get("product_name")), str(payload.get("product_version"))))
    return product_keys


def _coverage_treatments(coverage_path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    payload = _load_json(coverage_path)
    treatments: dict[tuple[str, str], dict[str, Any]] = {}
    for treatment in payload.get("treatments", []):
        if not isinstance(treatment, dict):
            continue
        treatments[(str(treatment.get("product_name")), str(treatment.get("product_version")))] = (
            treatment
        )
    return treatments


def _validate_treatment_fields(
    *,
    treatment: dict[str, Any],
    product_key: tuple[str, str],
    snapshot_product_keys: set[tuple[str, str]],
) -> list[str]:
    product_name, product_version = product_key
    issues: list[str] = []
    status = treatment.get("coverage_status")
    if status not in SUPPORTED_COVERAGE_STATUSES:
        issues.append(
            f"{product_name}:{product_version}: unsupported trust telemetry coverage_status={status}"
        )
    for field_name in ("rationale", "owner", "decision_date"):
        if not str(treatment.get(field_name) or "").strip():
            issues.append(
                f"{product_name}:{product_version}: trust telemetry coverage missing {field_name}"
            )
    if status == CERTIFIED_STATIC_SNAPSHOT and product_key not in snapshot_product_keys:
        issues.append(
            f"{product_name}:{product_version}: coverage marks certified_static_snapshot but no "
            "matching static telemetry snapshot exists"
        )
    if status == PENDING_STATIC_SNAPSHOT and treatment.get("evidence_artifact") is not None:
        issues.append(
            f"{product_name}:{product_version}: pending_static_snapshot must not point to a "
            "certified evidence artifact"
        )
    return issues


def validate_trust_telemetry_coverage(
    *,
    source_directory: Path = LOCAL_TELEMETRY_DIR,
    product_declaration_path: Path = LOCAL_PRODUCT_DECLARATION_PATH,
    coverage_path: Path = LOCAL_TELEMETRY_COVERAGE_PATH,
) -> list[str]:
    if not product_declaration_path.exists():
        return [f"{product_declaration_path}: product declaration file does not exist"]
    if not coverage_path.exists():
        return [f"{coverage_path}: trust telemetry coverage contract does not exist"]

    active_product_keys = _active_product_keys(product_declaration_path)
    snapshot_product_keys = _snapshot_product_keys(source_directory)
    treatments = _coverage_treatments(coverage_path)
    treatment_keys = set(treatments)

    issues: list[str] = []
    for product_key in sorted(active_product_keys):
        if product_key not in snapshot_product_keys and product_key not in treatment_keys:
            issues.append(
                f"{product_key[0]}:{product_key[1]}: active product has no static trust "
                "telemetry snapshot or governed coverage treatment"
            )
            continue
        if product_key in treatment_keys:
            issues.extend(
                _validate_treatment_fields(
                    treatment=treatments[product_key],
                    product_key=product_key,
                    snapshot_product_keys=snapshot_product_keys,
                )
            )

    for product_key in sorted(treatment_keys - active_product_keys):
        issues.append(
            f"{product_key[0]}:{product_key[1]}: trust telemetry coverage references an "
            "unknown or inactive product"
        )
    return issues


def main() -> int:
    issues = validate_repo_native_trust_telemetry()
    if issues:
        for issue in issues:
            print(issue)
        return 1

    snapshot_count = len(list(LOCAL_TELEMETRY_DIR.glob("*.telemetry.v1.json")))
    print(
        f"Validated {snapshot_count} repo-native trust telemetry snapshot(s) "
        f"in {LOCAL_TELEMETRY_DIR}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
