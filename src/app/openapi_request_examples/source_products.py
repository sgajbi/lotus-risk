from typing import Any

JsonObject = dict[str, Any]


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


__all__ = [
    "MANDATE_HEALTH_EXAMPLES",
    "REGIME_SCENARIO_EXAMPLES",
    "RISK_EVENT_COHORT_EXAMPLES",
    "JsonObject",
]
