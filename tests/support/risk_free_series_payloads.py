from __future__ import annotations

from collections.abc import Iterable


def build_risk_free_series_response(
    *,
    currency: str = "USD",
    as_of_date: str = "2026-01-06",
    start_date: str = "2026-01-01",
    end_date: str = "2026-01-06",
    series_mode: str = "annualized_rate_series",
    points: Iterable[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "currency": currency,
        "as_of_date": as_of_date,
        "series_mode": series_mode,
        "resolved_window": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "frequency": "daily",
        "request_fingerprint": "rf-fingerprint",
        "points": list(points or []),
        "lineage": {
            "contract_version": "rfc_062_v1",
            "source_system": "lotus-core-query-service",
            "generated_by": "integration.risk_free_series",
        },
    }
