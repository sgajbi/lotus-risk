from __future__ import annotations

RISK_RESPONSE_EXAMPLE: dict[str, object] = {
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
            "aligned_benchmark_observation_count": 64,
            "benchmark_context": {
                "requested": True,
                "available": True,
                "aligned": True,
                "reason": "APPLIED",
                "requested_metric_count": 3,
                "requested_metrics": [
                    "BETA",
                    "TRACKING_ERROR",
                    "INFORMATION_RATIO",
                ],
            },
            "metrics": {
                "VOLATILITY": {
                    "value": 12.538011,
                    "details": {
                        "observation_count": 64,
                        "standard_deviation": 0.0078985986,
                        "annualization_factor": 252,
                    },
                },
                "SHARPE": {
                    "value": 2.029072,
                    "details": {
                        "observation_count": 64,
                        "annualization_factor": 252,
                        "mean_return": 0.0010093159,
                        "periodic_risk_free_rate": 0.0001,
                        "excess_return": 0.0009093159,
                        "annualized_excess_return": 0.229147604,
                        "volatility": 0.0078985986,
                    },
                },
                "BETA": {
                    "value": -0.08222479,
                    "details": {
                        "aligned_observation_count": 64,
                        "portfolio_mean_return": 0.0010093159,
                        "benchmark_mean_return": 0.0004210968,
                        "covariance": -0.0002246556,
                        "benchmark_variance": 0.0027322129,
                    },
                },
                "TRACKING_ERROR": {
                    "value": 9.79331573,
                    "details": {
                        "aligned_observation_count": 64,
                        "annualization_factor": 252,
                        "portfolio_mean_return": 0.0010093159,
                        "benchmark_mean_return": 0.0004210968,
                        "active_mean_return": 0.0005882191,
                        "active_volatility": 0.006169209,
                        "annualized_tracking_error": 0.0979331573,
                    },
                },
                "INFORMATION_RATIO": {
                    "value": 1.5135958,
                    "details": {
                        "aligned_observation_count": 64,
                        "annualization_factor": 252,
                        "portfolio_mean_return": 0.0010093159,
                        "benchmark_mean_return": 0.0004210968,
                        "active_mean_return": 0.0005882191,
                        "tracking_error": 0.006169209,
                        "annualized_active_return": 0.1482312153,
                        "annualized_tracking_error": 0.0979331573,
                    },
                },
                "VAR": {
                    "value": -1.55,
                    "details": {
                        "method": "HISTORICAL",
                        "confidence": 0.95,
                        "tail_probability": 0.05,
                        "base_horizon_days": 1,
                        "horizon_days": 4,
                        "horizon_scale_method": "SQRT_TIME",
                        "horizon_scale_factor": 2.0,
                        "include_expected_shortfall": True,
                        "base_var": -0.775,
                        "observation_count": 64,
                        "tail_observation_count": 5,
                        "base_expected_shortfall": -1.0,
                        "expected_shortfall_observation_count": 5,
                        "expected_shortfall": -2.0,
                    },
                },
            },
        }
    },
    "metadata": {
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
        "benchmark_context": {
            "requested": True,
            "requested_metrics": [
                "BETA",
                "TRACKING_ERROR",
                "INFORMATION_RATIO",
            ],
        },
        "mar_annual_rate": 0.0,
        "var_method": "HISTORICAL",
        "var_confidence": 0.95,
        "var_horizon_days": 4,
    },
}
