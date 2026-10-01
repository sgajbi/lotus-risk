from __future__ import annotations

from datetime import date, timedelta
from math import log, sqrt

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _daily_returns(values: list[float]) -> list[dict[str, float | str]]:
    start = date(2026, 1, 1)
    return [
        {"date": str(start + timedelta(days=index)), "value": value}
        for index, value in enumerate(values)
    ]


def _var_payload(
    *,
    frequency: str,
    method: str,
    horizon_days: int,
    use_log_returns: bool,
    values: list[float],
    metrics: list[str] | None = None,
) -> dict[str, object]:
    returns = _daily_returns(values)
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": returns[-1]["date"], "net_or_gross": "NET"},
            "portfolio_open_date": returns[0]["date"],
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": metrics if metrics is not None else ["VAR"],
            "options": {
                "frequency": frequency,
                "use_log_returns": use_log_returns,
                "var": {
                    "method": method,
                    "confidence": 0.95,
                    "horizon_days": horizon_days,
                    "include_expected_shortfall": True,
                },
            },
            "returns": returns,
        },
    }


@pytest.mark.parametrize("frequency", ["DAILY", "WEEKLY", "MONTHLY"])
@pytest.mark.parametrize("horizon_days", [1, 4])
@pytest.mark.parametrize("use_log_returns", [False, True])
def test_var_and_expected_shortfall_use_daily_sampling_across_report_frequencies(
    frequency: str,
    horizon_days: int,
    use_log_returns: bool,
) -> None:
    values = [-1.0] * 90  # Jan/Feb/Mar: partial weeks and unequal month lengths are intentional.
    response = TestClient(app).post(
        "/analytics/risk/calculate",
        json=_var_payload(
            frequency=frequency,
            method="HISTORICAL",
            horizon_days=horizon_days,
            use_log_returns=use_log_returns,
            values=values,
        ),
    )

    assert response.status_code == 200
    metric = response.json()["results"]["YTD"]["metrics"]["VAR"]
    expected_base = log(0.99) * 100 if use_log_returns else -1.0
    expected_value = expected_base * sqrt(horizon_days)
    assert metric["value"] == pytest.approx(expected_value)
    details = metric["details"]
    assert details["base_var"] == pytest.approx(expected_base)
    assert details["base_expected_shortfall"] == pytest.approx(expected_base)
    assert details["expected_shortfall"] == pytest.approx(expected_value)
    assert details["sampling_frequency"] == "DAILY"
    assert details["base_horizon_days"] == 1
    assert details["horizon_days"] == horizon_days
    assert details["horizon_scale_factor"] == pytest.approx(sqrt(horizon_days))
    assert details["observation_count"] == 90
    assert details["tail_observation_count"] == 90


@pytest.mark.parametrize("method", ["HISTORICAL", "GAUSSIAN", "CORNISH_FISHER"])
@pytest.mark.parametrize("frequency", ["WEEKLY", "MONTHLY"])
def test_all_var_methods_match_daily_distribution_when_reporting_frequency_is_non_daily(
    method: str,
    frequency: str,
) -> None:
    values = [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0] * 15
    daily_response = TestClient(app).post(
        "/analytics/risk/calculate",
        json=_var_payload(
            frequency="DAILY",
            method=method,
            horizon_days=1,
            use_log_returns=False,
            values=values,
        ),
    )
    non_daily_response = TestClient(app).post(
        "/analytics/risk/calculate",
        json=_var_payload(
            frequency=frequency,
            method=method,
            horizon_days=1,
            use_log_returns=False,
            values=values,
        ),
    )

    assert daily_response.status_code == 200
    assert non_daily_response.status_code == 200
    daily_metric = daily_response.json()["results"]["YTD"]["metrics"]["VAR"]
    non_daily_metric = non_daily_response.json()["results"]["YTD"]["metrics"]["VAR"]
    assert non_daily_metric["value"] == pytest.approx(daily_metric["value"])
    assert non_daily_metric["details"]["base_var"] == pytest.approx(
        daily_metric["details"]["base_var"]
    )
    assert non_daily_metric["details"]["expected_shortfall"] == pytest.approx(
        daily_metric["details"]["expected_shortfall"]
    )
    assert non_daily_metric["details"]["sampling_frequency"] == "DAILY"
    assert non_daily_metric["details"]["observation_count"] == len(values)


def test_weekly_mixed_metrics_keep_daily_var_and_resample_volatility() -> None:
    values = [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0] * 15
    response = TestClient(app).post(
        "/analytics/risk/calculate",
        json=_var_payload(
            frequency="WEEKLY",
            method="HISTORICAL",
            horizon_days=1,
            use_log_returns=False,
            values=values,
            metrics=["VAR", "VOLATILITY"],
        ),
    )

    assert response.status_code == 200
    metrics = response.json()["results"]["YTD"]["metrics"]
    assert metrics["VAR"]["details"]["sampling_frequency"] == "DAILY"
    assert metrics["VAR"]["details"]["observation_count"] == len(values)
    assert metrics["VOLATILITY"]["details"]["observation_count"] < len(values)
