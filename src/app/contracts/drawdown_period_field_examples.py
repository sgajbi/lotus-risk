from __future__ import annotations

from typing import Any

DRAWDOWN_PERIOD_SUMMARY_EXAMPLE: dict[str, Any] = {"max_drawdown": -0.124533}

DRAWDOWN_PERIOD_EPISODES_EXAMPLE: Any = [
    {
        "episode_id": "dd_0001",
        "peak_date": "2026-01-12",
        "trough_date": "2026-02-03",
        "recovery_date": None,
        "depth": -0.124533,
        "days_to_trough": 16,
        "days_to_recovery": None,
        "total_days": 34,
        "is_recovered": False,
    }
]

DRAWDOWN_PERIOD_RELATIVE_TO_BENCHMARK_EXAMPLE: dict[str, Any] = {
    "max_drawdown": -0.0821,
    "max_drawdown_peak_date": "2026-01-11",
    "max_drawdown_trough_date": "2026-02-01",
    "max_drawdown_recovery_date": "2026-02-18",
    "is_recovered": True,
    "days_to_trough": 15,
    "days_to_recovery": 9,
    "time_under_water_days": 21,
}

DRAWDOWN_PERIOD_RELATIVE_CONTEXT_EXAMPLE: dict[str, Any] = {
    "requested": True,
    "applied": True,
    "reason": "APPLIED",
    "aligned_observation_count": 64,
}

DRAWDOWN_PERIOD_UNDERWATER_SERIES_EXAMPLE: Any = [{"date": "2026-01-20", "drawdown": -0.0521}]

__all__ = [
    "DRAWDOWN_PERIOD_EPISODES_EXAMPLE",
    "DRAWDOWN_PERIOD_RELATIVE_CONTEXT_EXAMPLE",
    "DRAWDOWN_PERIOD_RELATIVE_TO_BENCHMARK_EXAMPLE",
    "DRAWDOWN_PERIOD_SUMMARY_EXAMPLE",
    "DRAWDOWN_PERIOD_UNDERWATER_SERIES_EXAMPLE",
]
