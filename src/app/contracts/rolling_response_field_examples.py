from __future__ import annotations

from typing import Any

ROLLING_REQUESTED_METRICS_EXAMPLE: Any = [
    "ROLLING_VOLATILITY",
    "ROLLING_SHARPE",
    "ROLLING_BETA",
]

ROLLING_BENCHMARK_CONTEXT_EXAMPLE: dict[str, Any] = {
    "requested": True,
    "requested_metrics": [
        "ROLLING_BETA",
        "ROLLING_TRACKING_ERROR",
    ],
}

ROLLING_RISK_FREE_CONTEXT_EXAMPLE: dict[str, Any] = {
    "requested": True,
    "requested_metrics": ["ROLLING_SHARPE"],
}

ROLLING_CALCULATION_SUPPORTABILITY_EXAMPLE: dict[str, Any] = {
    "state": "ready",
    "reason": "calculation_complete",
    "freshness_bucket": "current",
    "degraded_metric_count": 0,
    "empty_period_count": 0,
    "evaluated_period_count": 1,
}

ROLLING_RESPONSE_SCOPE_EXAMPLE: dict[str, Any] = {
    "as_of_date": "2026-02-28",
    "reporting_currency": "USD",
    "net_or_gross": "NET",
}

ROLLING_RESPONSE_RESULTS_EXAMPLE: dict[str, Any] = {
    "YTD": {
        "start_date": "2026-01-01",
        "end_date": "2026-02-28",
        "series_count": 41,
        "benchmark_series_count": 41,
        "aligned_benchmark_series_count": 41,
        "window_lengths_requested": [21, 63],
        "window_count_requested": 2,
        "window_lengths_emitted": [21, 63],
        "window_count_emitted": 2,
        "benchmark_context": {
            "requested": True,
            "available": True,
            "aligned": True,
            "reason": "APPLIED",
        },
        "risk_free_series_count": 41,
        "aligned_risk_free_series_count": 41,
        "risk_free_context": {
            "requested": True,
            "available": True,
            "aligned": True,
            "reason": "APPLIED",
        },
        "window_results": [],
        "quality_flags": [],
        "error": None,
    }
}

ROLLING_RESPONSE_METADATA_EXAMPLE: dict[str, Any] = {
    "contract_version": "v1",
    "methodology_version": "rolling_metrics.v1",
    "annualization_basis": 252,
    "metric_unit_semantics": {
        "ROLLING_VOLATILITY": "decimal_ratio",
        "ROLLING_BETA": "unitless",
        "ROLLING_TRACKING_ERROR": "decimal_ratio",
    },
    "requested_metrics": [
        "ROLLING_VOLATILITY",
        "ROLLING_BETA",
        "ROLLING_TRACKING_ERROR",
    ],
    "window_lengths_requested": [21, 63],
    "window_count_requested": 2,
    "alignment_policy": "INNER_JOIN",
    "min_observations_policy": "STRICT",
    "include_time_series": False,
    "benchmark_context": ROLLING_BENCHMARK_CONTEXT_EXAMPLE,
    "risk_free_context": {
        "requested": False,
        "requested_metrics": [],
    },
}

__all__ = [
    "ROLLING_BENCHMARK_CONTEXT_EXAMPLE",
    "ROLLING_CALCULATION_SUPPORTABILITY_EXAMPLE",
    "ROLLING_REQUESTED_METRICS_EXAMPLE",
    "ROLLING_RESPONSE_METADATA_EXAMPLE",
    "ROLLING_RESPONSE_RESULTS_EXAMPLE",
    "ROLLING_RESPONSE_SCOPE_EXAMPLE",
    "ROLLING_RISK_FREE_CONTEXT_EXAMPLE",
]
