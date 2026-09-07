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
                    # An ACTIVE_RISK set as the service actually returns one. The
                    # previous figures here could not occur: `weight_average` carries
                    # the ACTIVE weight, portfolio minus benchmark, so three positive
                    # averages totalling 0.841 described a portfolio 84 points
                    # overweight in aggregate against a fully allocated benchmark.
                    #
                    # The residual being the whole metric is not a defect in this
                    # example -- it is what the decomposition currently produces, and
                    # it is why `lotus-risk#283` exists. Active weights sum to zero
                    # for fully allocated histories, so the components do too. An
                    # example showing a neatly allocated active decomposition would
                    # teach a contract the service cannot honour, which is the exact
                    # failure `test_attribution_example_reconciles` was written for.
                    "total_value": 0.0642,
                    "reconciled_sum": 0.0,
                    "residual": 0.0642,
                    "contributors": [
                        {
                            "group_key": "SECTOR_TECH",
                            "group_label": "Technology",
                            # Overweight: +20 points against the benchmark.
                            "weight_average": 0.2,
                            "marginal_contribution": 0.0642,
                            "component_contribution": 0.01284,
                            "percent_contribution": 0.2,
                        },
                        {
                            "group_key": "SECTOR_HEALTH",
                            "group_label": "Healthcare",
                            "weight_average": -0.065,
                            "marginal_contribution": 0.0642,
                            "component_contribution": -0.004173,
                            "percent_contribution": -0.065,
                        },
                        {
                            "group_key": "SECTOR_FIN",
                            "group_label": "Financials",
                            "weight_average": -0.135,
                            "marginal_contribution": 0.0642,
                            "component_contribution": -0.008667,
                            "percent_contribution": -0.135,
                        },
                    ],
                    # Every marginal is the same 0.0642 -- the portfolio-level
                    # tracking error -- which is the caveat stated on the field:
                    # under constant weights it is not group-specific.
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
