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
        "data_policy": {
            "missing_data_policy": "ALLOW_PARTIAL",
            "fill_method": "NONE",
            "calendar_policy": "BUSINESS",
        },
        "input_mode": "stateful",
        "stateful_input": {},
    }
