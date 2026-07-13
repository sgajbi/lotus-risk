from __future__ import annotations

from app.services.observability_ports import (
    record_analytics_freshness_bucket,
    record_calculation_supportability,
)

SOURCE_PRODUCT_REASON_BY_STATE = {
    "ready": "calculation_complete",
    "attention": "source_product_attention",
    "unavailable": "source_product_unavailable",
    "degraded": "source_product_degraded",
    "pending_review": "source_product_pending_review",
    "blocked": "source_product_blocked",
}


def record_source_product_supportability(
    *,
    operation: str,
    supportability_state: str,
    freshness_bucket: str = "unknown",
) -> None:
    reason = SOURCE_PRODUCT_REASON_BY_STATE.get(supportability_state, "unknown")
    record_calculation_supportability(
        operation=operation,
        supportability_state=supportability_state,
        reason=reason,
        freshness_bucket=freshness_bucket,
    )
    record_analytics_freshness_bucket(
        operation=operation,
        freshness_bucket=freshness_bucket,
        supportability_state=supportability_state,
    )
