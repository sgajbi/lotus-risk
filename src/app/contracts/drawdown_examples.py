from __future__ import annotations

DRAWDOWN_REQUEST_EXAMPLES: list[dict[str, object]] = [
    {
        "input_mode": "stateless",
        "benchmark_policy": {
            "include_benchmark": True,
            "missing_benchmark_policy": "REQUIRE",
        },
        "stateless_input": {
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
        },
        "analysis_options": {
            "include_underwater_series": True,
            "include_episode_list": True,
            "top_n_episodes": 3,
            "cdar_alpha": 0.95,
            "minimum_episode_depth_bps": 0.0,
            "duration_unit": "BUSINESS_DAYS",
        },
    },
    {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-03-31",
            "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
            "reporting_currency": "USD",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "benchmark_policy": {
                "include_benchmark": True,
                "missing_benchmark_policy": "REQUIRE",
            },
        },
        "analysis_options": {
            "include_underwater_series": False,
            "include_episode_list": True,
            "top_n_episodes": 5,
            "cdar_alpha": 0.95,
            "minimum_episode_depth_bps": 25.0,
            "duration_unit": "BUSINESS_DAYS",
        },
    },
]


DRAWDOWN_RESPONSE_EXAMPLES: list[dict[str, object]] = [
    {
        "source_service": "lotus-risk",
        "input_mode": "stateful",
        "scope": {
            "as_of_date": "2026-03-31",
            "reporting_currency": "USD",
            "net_or_gross": "NET",
        },
        "results": {
            "YTD": {
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "portfolio_observation_count": 64,
                "benchmark_observation_count": 64,
                "summary": {
                    "max_drawdown": -0.084211,
                    "max_drawdown_peak_date": "2026-01-11",
                    "max_drawdown_trough_date": "2026-02-03",
                    "max_drawdown_recovery_date": "2026-02-19",
                    "is_recovered": True,
                    "days_to_trough": 16,
                    "days_to_recovery": 11,
                    "time_under_water_days": 27,
                    "average_drawdown": -0.041208,
                    "ulcer_index": 0.053901,
                    "drawdown_at_risk_95": -0.0812,
                    "conditional_drawdown_at_risk_95": -0.084211,
                },
                "episodes": [
                    {
                        "episode_id": "dd_0001",
                        "peak_date": "2026-01-11",
                        "trough_date": "2026-02-03",
                        "recovery_date": "2026-02-19",
                        "depth": -0.084211,
                        "days_to_trough": 16,
                        "days_to_recovery": 11,
                        "total_days": 27,
                        "is_recovered": True,
                    }
                ],
                "relative_to_benchmark": {
                    "max_drawdown": -0.026414,
                    "max_drawdown_peak_date": "2026-01-04",
                    "max_drawdown_trough_date": "2026-02-15",
                    "max_drawdown_recovery_date": "2026-02-28",
                    "is_recovered": True,
                    "days_to_trough": 30,
                    "days_to_recovery": 10,
                    "time_under_water_days": 74,
                },
                "relative_to_benchmark_context": {
                    "requested": True,
                    "applied": True,
                    "reason": "APPLIED",
                    "aligned_observation_count": 64,
                },
                "underwater_series": [
                    {"date": "2026-01-01", "drawdown": 0.0},
                    {"date": "2026-01-02", "drawdown": -0.0121},
                ],
                "error": None,
            }
        },
        "metadata": {
            "contract_version": "v1",
            "methodology_version": "drawdown.v1",
            "include_underwater_series": True,
            "include_episode_list": True,
            "top_n_episodes": 5,
            "cdar_alpha": 0.95,
            "minimum_episode_depth_bps": 25.0,
            "duration_unit": "BUSINESS_DAYS",
            "include_benchmark": True,
            "missing_benchmark_policy": "REQUIRE",
        },
    }
]
