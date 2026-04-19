from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_PRODUCER_DECLARATION_PATH = (
    REPO_ROOT / "contracts" / "domain-data-products" / "lotus-risk-products.v1.json"
)
LOCAL_CONSUMER_DECLARATION_PATH = (
    REPO_ROOT / "contracts" / "domain-data-products" / "lotus-risk-consumers.v1.json"
)
REPO_RELATIVE_PRODUCER_DECLARATION_PATH = LOCAL_PRODUCER_DECLARATION_PATH.relative_to(REPO_ROOT)
REPO_RELATIVE_CONSUMER_DECLARATION_PATH = LOCAL_CONSUMER_DECLARATION_PATH.relative_to(REPO_ROOT)


@lru_cache(maxsize=1)
def load_local_producer_declaration() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(LOCAL_PRODUCER_DECLARATION_PATH.read_text(encoding="utf-8")),
    )


@lru_cache(maxsize=1)
def load_local_consumer_declaration() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(LOCAL_CONSUMER_DECLARATION_PATH.read_text(encoding="utf-8")),
    )


def list_declared_products() -> list[dict[str, Any]]:
    payload = load_local_producer_declaration()
    products = payload.get("products", [])
    return [product for product in products if isinstance(product, dict)]


def get_local_producer_declaration_fingerprint() -> str:
    payload = load_local_producer_declaration()
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def list_declared_dependencies() -> list[dict[str, Any]]:
    payload = load_local_consumer_declaration()
    dependencies = payload.get("dependencies", [])
    return [dependency for dependency in dependencies if isinstance(dependency, dict)]


def get_local_consumer_declaration_fingerprint() -> str:
    payload = load_local_consumer_declaration()
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_declared_product(*, product_name: str, product_version: str) -> dict[str, Any]:
    for product in list_declared_products():
        if (
            product.get("product_name") == product_name
            and product.get("product_version") == product_version
        ):
            return product
    raise ValueError(
        f"Unknown lotus-risk declared product {product_name} {product_version} in "
        f"{LOCAL_PRODUCER_DECLARATION_PATH}"
    )
