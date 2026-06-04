from __future__ import annotations

CONCENTRATION_REQUEST_EXAMPLES: list[dict[str, object]] = [
    {
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
    },
    {
        "input_mode": "stateful",
        "issuer_grouping_level": "ultimate_parent",
        "enrichment_policy": "merge_caller_then_core",
        "stateful_input": {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-03-31",
            "reporting_currency": "USD",
            "include_cash_positions": True,
            "include_zero_quantity_positions": False,
            "top_n": 10,
        },
    },
    {
        "input_mode": "simulation",
        "issuer_grouping_level": "ultimate_parent",
        "simulation_input": {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "as_of_date": "2026-03-31",
            "top_n": 10,
            "simulation_changes": [
                {
                    "security_id": "FO_EQ_AAPL_US",
                    "transaction_type": "BUY",
                    "quantity": 10,
                }
            ],
        },
    },
]


CONCENTRATION_RESPONSE_EXAMPLES: list[dict[str, object]] = [
    {
        "source_service": "lotus-risk",
        "input_mode": "stateful",
        "risk_proxy": {
            "hhi_current": 1345.677131,
            "hhi_proposed": 1345.677131,
            "hhi_delta": 0.0,
        },
        "single_position_concentration": {
            "top_position_weight_current": 0.23014,
            "top_position_weight_proposed": 0.23014,
            "top_position_weight_delta": 0.0,
            "top_n_cumulative_weight_current": 0.992137,
            "top_n_cumulative_weight_proposed": 0.992137,
            "top_n_cumulative_weight_delta": 0.0,
            "top_n": 10,
            "top_position_current": {
                "security_id": "FO_FUND_PIMCO_INC",
                "security_name": "PIMCO GIS Income Fund",
                "weight": 0.23014,
            },
            "top_position_proposed": {
                "security_id": "FO_FUND_PIMCO_INC",
                "security_name": "PIMCO GIS Income Fund",
                "weight": 0.23014,
            },
        },
        "issuer_concentration": {
            "hhi_current": 1666.519669,
            "hhi_proposed": 1666.519669,
            "hhi_delta": 0.0,
            "top_issuer_weight_current": 0.245075,
            "top_issuer_weight_proposed": 0.245075,
            "top_issuer_weight_delta": 0.0,
            "coverage_status": "complete",
            "covered_position_count_current": 11,
            "covered_position_count_proposed": 11,
            "total_position_count_current": 11,
            "total_position_count_proposed": 11,
            "uncovered_position_count_current": 0,
            "uncovered_position_count_proposed": 0,
            "coverage_ratio_current": 1.0,
            "coverage_ratio_proposed": 1.0,
            "note": None,
            "top_issuer_current": {
                "issuer_id": "ULTIMATE_BLACKROCK",
                "issuer_name": "BlackRock, Inc.",
                "weight": 0.245075,
            },
            "top_issuer_proposed": {
                "issuer_id": "ULTIMATE_BLACKROCK",
                "issuer_name": "BlackRock, Inc.",
                "weight": 0.245075,
            },
        },
        "valuation_context": {
            "portfolio_currency": "USD",
            "reporting_currency": "USD",
            "position_basis": "market_value_base",
            "weight_basis": "total_market_value_base",
        },
        "metadata": {
            "as_of_date": "2026-03-31",
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "simulation_session_id": None,
            "simulation_session_version": None,
            "session_expires_at": None,
            "issuer_grouping_level": "ultimate_parent",
            "enrichment_policy": "merge_caller_then_core",
            "include_cash_positions": True,
            "include_zero_quantity_positions": False,
        },
    }
]
