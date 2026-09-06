from __future__ import annotations

HISTORICAL_ATTRIBUTION_REQUEST_EXAMPLE: dict[str, object] = {
    "input_mode": "stateful",
    "stateful_input": {
        "portfolio_id": "DEMO_DPM_EUR_001",
        "as_of_date": "2026-02-28",
        "reporting_currency": "USD",
        "net_or_gross": "NET",
        "periods": [{"type": "YTD", "name": "YTD"}],
        "attribution_options": {
            "attribution_types": ["ACTIVE_RISK"],
            "metrics": ["TRACKING_ERROR"],
            "grouping_dimensions": ["SECTOR"],
            "annualization_basis": 252,
            "covariance_method": "EMPIRICAL",
            "min_observations_policy": "STRICT",
        },
    },
}


HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE: dict[str, object] = {
    "source_service": "lotus-risk",
    "input_mode": "stateful",
    "scope": {
        "as_of_date": "2026-02-28",
        "reporting_currency": "USD",
        "net_or_gross": "NET",
    },
    "results": {
        "YTD": {
            "start_date": "2026-01-01",
            "end_date": "2026-02-28",
            "attribution_sets": [
                {
                    "attribution_type": "ACTIVE_RISK",
                    "metric": "TRACKING_ERROR",
                    "grouping_dimension": "SECTOR",
                    "total_value": 0.0642,
                    "reconciled_sum": 0.0638,
                    "residual": 0.0004,
                    "contributors": [
                        {
                            "group_key": "SECTOR_TECH",
                            "group_label": "Technology",
                            "weight_average": 0.245,
                            "marginal_contribution": 0.0910,
                            "component_contribution": 0.0223,
                            "percent_contribution": 0.3474,
                        },
                        {
                            "group_key": "SECTOR_HEALTH",
                            "group_label": "Healthcare",
                            "weight_average": 0.184,
                            "marginal_contribution": -0.0310,
                            "component_contribution": -0.0057,
                            "percent_contribution": -0.0888,
                        },
                        {
                            "group_key": "SECTOR_FIN",
                            "group_label": "Financials",
                            "weight_average": 0.412,
                            "marginal_contribution": 0.1146,
                            "component_contribution": 0.0472,
                            "percent_contribution": 0.7352,
                        },
                    ],
                    "quality_flags": [],
                }
            ],
            "error": None,
        }
    },
    "metadata": {
        "contract_version": "v1",
        "methodology_version": "historical_attribution.v1",
        "covariance_method": "EMPIRICAL",
        "annualization_basis": 252,
        "metric_unit_semantics": {"TRACKING_ERROR": "decimal_ratio"},
        "requested_attribution_types": ["ACTIVE_RISK"],
        "requested_metrics": ["TRACKING_ERROR"],
        "requested_grouping_dimensions": ["SECTOR"],
        "min_observations_policy": "STRICT",
        "stateful_active_risk_supported_grouping_dimensions": [
            "POSITION",
            "SECTOR",
            "ASSET_CLASS",
            "ISSUER",
        ],
        "stateful_active_risk_gated_grouping_dimensions": [],
        "stateful_active_risk_gate_reason": "none",
    },
}
