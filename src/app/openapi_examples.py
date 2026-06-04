from typing import Any

JsonObject = dict[str, Any]


def request_body_examples(examples: dict[str, JsonObject]) -> JsonObject:
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {name: {"value": value} for name, value in examples.items()}
                }
            }
        }
    }


RISK_CALCULATE_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2025-03-31", "net_or_gross": "NET"},
            "portfolio_open_date": "2024-01-01",
            "periods": [
                {
                    "type": "EXPLICIT",
                    "name": "Explicit",
                    "from_date": "2025-01-01",
                    "to_date": "2025-03-31",
                }
            ],
            "metrics": ["VOLATILITY", "SHARPE", "VAR"],
            "options": {
                "frequency": "DAILY",
                "risk_free_mode": "ANNUAL_RATE",
                "risk_free_annual_rate": 0.01,
                "var": {
                    "method": "HISTORICAL",
                    "confidence": 0.95,
                    "horizon_days": 1,
                    "include_expected_shortfall": True,
                },
            },
            "returns": [
                {"date": "2025-01-02", "value": 1.0},
                {"date": "2025-01-03", "value": 2.0},
                {"date": "2025-01-06", "value": -1.0},
                {"date": "2025-01-07", "value": 0.5},
            ],
        },
    },
    "stateful": {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-02-27",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY", "SHARPE", "VAR"],
            "include_benchmark": True,
        },
    },
}


DRAWDOWN_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-05", "value": -2.0},
                {"date": "2026-01-06", "value": 0.5},
            ],
        },
        "analysis_options": {"include_underwater_series": True},
    }
}


ROLLING_METRICS_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-08", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -2.0},
                {"date": "2026-01-04", "value": 0.5},
                {"date": "2026-01-05", "value": 1.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-03", "value": -1.5},
                {"date": "2026-01-04", "value": 0.4},
                {"date": "2026-01-05", "value": 1.0},
            ],
            "risk_free_returns": [
                {"date": "2026-01-02", "value": 0.01},
                {"date": "2026-01-03", "value": 0.01},
                {"date": "2026-01-04", "value": 0.01},
                {"date": "2026-01-05", "value": 0.01},
            ],
            "rolling_options": {
                "window_lengths": [3],
                "metrics": [
                    "ROLLING_VOLATILITY",
                    "ROLLING_SHARPE",
                    "ROLLING_BETA",
                ],
                "include_time_series": True,
            },
        },
    }
}


CONCENTRATION_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "input_mode": "stateless",
        "issuer_grouping_level": "legal_issuer",
        "enrichment_policy": "use_caller_only",
        "stateless_input": {
            "current_positions": [
                {
                    "security_id": "AAA",
                    "security_name": "Alpha Fund",
                    "quantity": 50,
                    "issuer_id": "ISSUER_ALPHA",
                },
                {
                    "security_id": "BBB",
                    "security_name": "Beta Bond",
                    "quantity": 30,
                    "issuer_id": "ISSUER_BETA",
                },
            ],
            "projected_positions": [
                {
                    "security_id": "AAA",
                    "security_name": "Alpha Fund",
                    "proposed_quantity": 45,
                    "issuer_id": "ISSUER_ALPHA",
                },
                {
                    "security_id": "BBB",
                    "security_name": "Beta Bond",
                    "proposed_quantity": 35,
                    "issuer_id": "ISSUER_BETA",
                },
            ],
            "top_n": 2,
        },
    }
}


HISTORICAL_ATTRIBUTION_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-05", "value": -0.4},
                {"date": "2026-01-06", "value": 0.3},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-05", "value": -0.3},
                {"date": "2026-01-06", "value": 0.2},
            ],
            "exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.55,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.45,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.50,
                },
            ],
            "attribution_options": {
                "attribution_mode": "TOTAL_RISK",
                "grouping_dimension": "SECTOR",
            },
        },
    }
}


MANDATE_HEALTH_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "scope": {
            "as_of_date": "2026-02-27",
            "reporting_currency": "USD",
            "net_or_gross": "NET",
        },
        "period": {"type": "YTD", "name": "YTD"},
        "portfolio_open_date": "2024-01-01",
        "returns": [
            {"date": "2026-01-02", "value": 0.25},
            {"date": "2026-01-03", "value": -0.10},
            {"date": "2026-01-04", "value": 0.40},
        ],
        "benchmark_returns": [
            {"date": "2026-01-02", "value": 0.10},
            {"date": "2026-01-03", "value": 0.05},
            {"date": "2026-01-04", "value": 0.12},
        ],
        "tracking_error_attention_threshold": "0.01",
    }
}


REGIME_SCENARIO_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "as_of_date": "2026-05-03",
        "maximum_allowed_loss_pct": 0.12,
        "exposures": [
            {"bucket": "EQUITY", "weight": 0.55},
            {"bucket": "FIXED_INCOME", "weight": 0.35},
            {"bucket": "CASH", "weight": 0.10},
        ],
    }
}


RISK_EVENT_COHORT_EXAMPLES: dict[str, JsonObject] = {
    "stateless": {
        "risk_event_id": "RISK_EVENT_2026_Q2_RATES_UP",
        "as_of_date": "2026-05-10",
        "minimum_impact_score": 0.05,
        "portfolios": [
            {
                "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                "mandate_id": "MANDATE-PB-SG-GLOBAL-BAL-001",
                "portfolio_manager_id": "pm-singapore-01",
                "exposure_weights": {
                    "EQUITY": 0.55,
                    "FIXED_INCOME": 0.35,
                    "CASH": 0.10,
                },
            }
        ],
    }
}
