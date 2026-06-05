from __future__ import annotations

from typing import Any

APPROVED_CONSUMER_EXAMPLES: list[Any] = ["lotus-gateway"]
CURRENT_ROUTE_EXAMPLES: list[Any] = ["/analytics/risk/calculate"]
DEPENDENCY_SIGNAL_EXAMPLES: list[Any] = [
    {
        "service": "lotus-performance",
        "status": "degraded",
        "detail": "high_latency",
        "category": "transport",
        "issue_code": "UPSTREAM_HIGH_LATENCY",
    }
]
REQUIRED_TRUST_METADATA_EXAMPLES: list[Any] = ["product_name", "product_version", "as_of_date"]
SOURCE_SERVICE_EXAMPLES: list[Any] = ["lotus-risk", "lotus-performance"]
UPSTREAM_REQUEST_FINGERPRINT_EXAMPLE: dict[str, Any] = {
    "lotus-performance:/integration/returns/series": (
        "sha256:8d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a1"
    )
}

__all__ = [
    "APPROVED_CONSUMER_EXAMPLES",
    "CURRENT_ROUTE_EXAMPLES",
    "DEPENDENCY_SIGNAL_EXAMPLES",
    "REQUIRED_TRUST_METADATA_EXAMPLES",
    "SOURCE_SERVICE_EXAMPLES",
    "UPSTREAM_REQUEST_FINGERPRINT_EXAMPLE",
]
