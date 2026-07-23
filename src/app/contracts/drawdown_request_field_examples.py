from __future__ import annotations

from typing import Any

DRAWDOWN_STATELESS_INPUT_EXAMPLE: dict[str, Any] = {
    "scope": {
        "as_of_date": "2026-03-31",
        "reporting_currency": "USD",
        "net_or_gross": "NET",
    },
    "periods": [{"type": "YTD", "name": "YTD"}],
    "returns": [
        {"date": "2026-01-02", "value": 0.82},
        {"date": "2026-01-03", "value": -1.45},
        {"date": "2026-01-04", "value": 0.37},
    ],
    "benchmark_returns": [
        {"date": "2026-01-02", "value": 0.61},
        {"date": "2026-01-03", "value": -0.98},
        {"date": "2026-01-04", "value": 0.21},
    ],
}

DRAWDOWN_STATEFUL_INPUT_EXAMPLE: dict[str, Any] = {
    "portfolio_id": "PB_SG_GLOBAL_BAL_001",
    "as_of_date": "2026-03-31",
    "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
    "reporting_currency": "USD",
    "periods": [{"type": "YTD", "name": "YTD"}],
    "benchmark_policy": {
        "include_benchmark": True,
        "missing_benchmark_policy": "REQUIRE",
    },
}

DRAWDOWN_BENCHMARK_POLICY_EXAMPLE: dict[str, Any] = {
    "include_benchmark": True,
    "missing_benchmark_policy": "REQUIRE",
}

DRAWDOWN_ANALYSIS_OPTIONS_EXAMPLE: dict[str, Any] = {
    "include_underwater_series": True,
    "include_episode_list": True,
    "top_n_episodes": 5,
    "cdar_alpha": 0.95,
    "minimum_episode_depth_bps": 25.0,
    "duration_unit": "BUSINESS_DAYS",
}

__all__ = [
    "DRAWDOWN_ANALYSIS_OPTIONS_EXAMPLE",
    "DRAWDOWN_BENCHMARK_POLICY_EXAMPLE",
    "DRAWDOWN_STATEFUL_INPUT_EXAMPLE",
    "DRAWDOWN_STATELESS_INPUT_EXAMPLE",
]
