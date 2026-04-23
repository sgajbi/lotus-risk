from __future__ import annotations

from datetime import date

from app.contracts.risk import RiskRequestPeriod
from app.services.stateful_returns_request import build_stateful_returns_series_request


def test_build_stateful_returns_series_request_shapes_common_contract() -> None:
    periods = [RiskRequestPeriod.model_validate({"type": "YTD", "name": "YTD"})]

    payload = build_stateful_returns_series_request(
        portfolio_id="PB_SG_GLOBAL_BAL_001",
        as_of_date=date(2026, 3, 31),
        periods=periods,
        frequency="DAILY",
        metric_basis="NET",
        reporting_currency="USD",
        include_benchmark=True,
        include_risk_free=True,
        benchmark_id="BMK_PB_GLOBAL_BALANCED_60_40",
        missing_data_policy="ALLOW_PARTIAL",
    )

    assert payload == {
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "as_of_date": "2026-03-31",
        "window": {
            "mode": "EXPLICIT",
            "from_date": "2026-01-01",
            "to_date": "2026-03-31",
        },
        "frequency": "DAILY",
        "metric_basis": "NET",
        "reporting_currency": "USD",
        "series_selection": {
            "include_portfolio": True,
            "include_benchmark": True,
            "include_risk_free": True,
        },
        "benchmark": {
            "benchmark_id": "BMK_PB_GLOBAL_BALANCED_60_40",
            "return_source": "calculated",
        },
        "data_policy": {
            "missing_data_policy": "ALLOW_PARTIAL",
            "fill_method": "NONE",
            "calendar_policy": "BUSINESS",
        },
        "input_mode": "stateful",
        "stateful_input": {},
    }


def test_build_stateful_returns_series_request_preserves_null_reporting_currency_and_fail_fast_policy() -> (
    None
):
    periods = [RiskRequestPeriod.model_validate({"type": "YTD", "name": "YTD"})]

    payload = build_stateful_returns_series_request(
        portfolio_id="PB_SG_GLOBAL_BAL_001",
        as_of_date=date(2026, 3, 31),
        periods=periods,
        frequency="DAILY",
        metric_basis="GROSS",
        reporting_currency=None,
        include_benchmark=False,
        include_risk_free=False,
        missing_data_policy="FAIL_FAST",
    )

    assert payload["reporting_currency"] is None
    assert payload["metric_basis"] == "GROSS"
    assert payload["series_selection"] == {
        "include_portfolio": True,
        "include_benchmark": False,
        "include_risk_free": False,
    }
    assert payload["data_policy"] == {
        "missing_data_policy": "FAIL_FAST",
        "fill_method": "NONE",
        "calendar_policy": "BUSINESS",
    }


def test_build_stateful_returns_series_request_uses_since_inception_window_when_requested() -> None:
    periods = [RiskRequestPeriod.model_validate({"type": "SI", "name": "SI"})]

    payload = build_stateful_returns_series_request(
        portfolio_id="PB_SG_GLOBAL_BAL_001",
        as_of_date=date(2026, 3, 31),
        periods=periods,
        frequency="DAILY",
        metric_basis="NET",
        reporting_currency="USD",
        include_benchmark=True,
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )

    assert payload["window"] == {"mode": "RELATIVE", "period": "SI"}


def test_build_stateful_returns_series_request_uses_longest_explicit_window_across_periods() -> (
    None
):
    periods = [
        RiskRequestPeriod.model_validate(
            {
                "type": "EXPLICIT",
                "name": "Trailing Month",
                "from_date": "2026-03-01",
                "to_date": "2026-03-31",
            }
        ),
        RiskRequestPeriod.model_validate({"type": "YTD", "name": "YTD"}),
        RiskRequestPeriod.model_validate(
            {
                "type": "EXPLICIT",
                "name": "Short Window",
                "from_date": "2026-03-15",
                "to_date": "2026-03-20",
            }
        ),
    ]

    payload = build_stateful_returns_series_request(
        portfolio_id="PB_SG_GLOBAL_BAL_001",
        as_of_date=date(2026, 3, 31),
        periods=periods,
        frequency="DAILY",
        metric_basis="NET",
        reporting_currency="USD",
        include_benchmark=True,
        include_risk_free=True,
        missing_data_policy="ALLOW_PARTIAL",
    )

    assert payload["window"] == {
        "mode": "EXPLICIT",
        "from_date": "2026-01-01",
        "to_date": "2026-03-31",
    }
