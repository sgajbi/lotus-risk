from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_PRODUCER_DECLARATION_PATH = (
    REPO_ROOT / "contracts" / "domain-data-products" / "lotus-risk-products.v1.json"
)


@lru_cache(maxsize=1)
def load_local_producer_declaration() -> dict[str, Any]:
    return json.loads(LOCAL_PRODUCER_DECLARATION_PATH.read_text(encoding="utf-8"))


def list_declared_products() -> list[dict[str, Any]]:
    payload = load_local_producer_declaration()
    products = payload.get("products", [])
    return [product for product in products if isinstance(product, dict)]


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
