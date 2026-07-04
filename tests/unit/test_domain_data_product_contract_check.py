from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.domain_data_product_contract_check import (
    _resolve_platform_root,
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


def test_platform_root_resolution_prefers_explicit_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    platform_root = tmp_path / "platform"
    (platform_root / "platform-contracts").mkdir(parents=True)

    monkeypatch.setenv("LOTUS_PLATFORM_ROOT", str(platform_root))

    assert _resolve_platform_root() == platform_root.resolve()


def test_platform_root_resolution_supports_nested_ci_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.domain_data_product_contract_check as validator

    repo_root = tmp_path / "lotus-risk"
    platform_root = repo_root / ".lotus-platform"
    (platform_root / "platform-contracts").mkdir(parents=True)

    monkeypatch.delenv("LOTUS_PLATFORM_ROOT", raising=False)
    monkeypatch.setattr(validator, "REPO_ROOT", repo_root)

    assert validator._resolve_platform_root() == platform_root.resolve()


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
