from __future__ import annotations

from typing import Any

RISK_FREE_CONTEXT_EXAMPLE: dict[str, Any] = {
    "requested": True,
    "applied": True,
    "reason": "ANNUAL_RATE_APPLIED",
    "periodic_rate": 0.00003949,
}

RISK_BENCHMARK_CONTEXT_EXAMPLE: dict[str, Any] = {
    "requested": True,
    "requested_metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
}

RISK_CALCULATION_SUPPORTABILITY_EXAMPLE: dict[str, Any] = {
    "state": "ready",
    "reason": "calculation_complete",
    "freshness_bucket": "current",
    "degraded_metric_count": 0,
    "empty_period_count": 0,
    "evaluated_period_count": 1,
}

RISK_RESPONSE_SCOPE_EXAMPLE: dict[str, Any] = {
    "as_of_date": "2025-03-31",
    "reporting_currency": "USD",
    "net_or_gross": "NET",
}

RISK_RESPONSE_RESULTS_EXAMPLE: dict[str, Any] = {
    "explicit_q1_2025": {
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "portfolio_observation_count": 64,
        "benchmark_observation_count": 64,
        "aligned_benchmark_observation_count": 61,
        "benchmark_context": {
            "requested": True,
            "available": True,
            "aligned": True,
            "reason": "APPLIED",
            "requested_metric_count": 3,
            "requested_metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
        },
        "metrics": {"VOLATILITY": {"value": 0.23}},
    }
}

RISK_RESPONSE_METADATA_EXAMPLE: dict[str, Any] = {
    "contract_version": "v1",
    "methodology_version": "risk.v1",
    "frequency": "DAILY",
    "annualization_factor": 252,
    "use_log_returns": False,
    "risk_free_mode": "ANNUAL_RATE",
    "risk_free_annual_rate": 0.025518911987694626,
    "risk_free_context": {
        "requested": True,
        "applied": True,
        "reason": "ANNUAL_RATE_APPLIED",
        "periodic_rate": 0.0001,
    },
    "benchmark_context": RISK_BENCHMARK_CONTEXT_EXAMPLE,
    "mar_annual_rate": 0.0,
    "var_method": "HISTORICAL",
    "var_confidence": 0.95,
    "var_horizon_days": 1,
}

__all__ = [
    "RISK_BENCHMARK_CONTEXT_EXAMPLE",
    "RISK_CALCULATION_SUPPORTABILITY_EXAMPLE",
    "RISK_FREE_CONTEXT_EXAMPLE",
    "RISK_RESPONSE_METADATA_EXAMPLE",
    "RISK_RESPONSE_RESULTS_EXAMPLE",
    "RISK_RESPONSE_SCOPE_EXAMPLE",
]
