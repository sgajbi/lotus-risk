from __future__ import annotations

from typing import Any

ROLLING_PERIOD_BENCHMARK_CONTEXT_EXAMPLE: dict[str, Any] = {
    "requested": True,
    "available": True,
    "aligned": True,
    "reason": "APPLIED",
}

ROLLING_PERIOD_RISK_FREE_CONTEXT_EXAMPLE: dict[str, Any] = {
    "requested": False,
    "available": False,
    "aligned": False,
    "reason": "NOT_REQUESTED",
}

ROLLING_PERIOD_WINDOW_RESULTS_EXAMPLE: Any = [{"window_length": 63, "metric_summaries": {}}]

ROLLING_PERIOD_QUALITY_FLAGS_EXAMPLE: Any = ["metric:ROLLING_BETA:benchmark_variance_zero"]

__all__ = [
    "ROLLING_PERIOD_BENCHMARK_CONTEXT_EXAMPLE",
    "ROLLING_PERIOD_QUALITY_FLAGS_EXAMPLE",
    "ROLLING_PERIOD_RISK_FREE_CONTEXT_EXAMPLE",
    "ROLLING_PERIOD_WINDOW_RESULTS_EXAMPLE",
]
