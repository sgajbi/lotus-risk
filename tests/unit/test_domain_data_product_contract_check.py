from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.domain_data_product_contract_check import (
    platform_validation_dependencies_available,
    validate_repo_native_contracts,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DECLARATIONS_DIR = REPO_ROOT / "contracts" / "domain-data-products"
PLATFORM_DECLARATIONS_DIR = (
    REPO_ROOT.parent / "lotus-platform" / "platform-contracts" / "domain-data-products"
)


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_repo_native_domain_data_product_gate_passes() -> None:
    if not platform_validation_dependencies_available():
        pytest.skip("lotus-platform validator checkout is not available in this environment")
    assert validate_repo_native_contracts() == []


def test_repo_native_declarations_match_transitional_platform_mirrors() -> None:
    if not platform_validation_dependencies_available():
        pytest.skip("lotus-platform validator checkout is not available in this environment")
    assert _load_json(LOCAL_DECLARATIONS_DIR / "lotus-risk-products.v1.json") == _load_json(
        PLATFORM_DECLARATIONS_DIR / "lotus-risk-products.v1.json"
    )
    assert _load_json(LOCAL_DECLARATIONS_DIR / "lotus-risk-consumers.v1.json") == _load_json(
        PLATFORM_DECLARATIONS_DIR / "lotus-risk-consumers.v1.json"
    )


def test_repo_native_declaration_directory_contains_expected_contract_files() -> None:
    paths = sorted(path.name for path in LOCAL_DECLARATIONS_DIR.glob("*.json"))
    assert paths == [
        "lotus-risk-consumers.v1.json",
        "lotus-risk-products.v1.json",
    ]
