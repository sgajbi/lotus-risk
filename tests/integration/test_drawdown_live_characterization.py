from __future__ import annotations

import math
import os
from collections.abc import Sequence

import httpx
import pytest

from tests.support.live_returns_series import extract_decimal_returns, fetch_live_returns_series


def _live_enabled() -> bool:
    return os.getenv("LOTUS_RISK_RUN_LIVE_DRAWDOWN") == "1"


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="set LOTUS_RISK_RUN_LIVE_DRAWDOWN=1 to run live drawdown reconciliation",
)


RISK_BASE_URL = os.getenv("LOTUS_RISK_BASE_URL", "http://localhost:8130")
PERFORMANCE_BASE_URL = os.getenv("LOTUS_PERFORMANCE_BASE_URL", "http://localhost:8002")
PORTFOLIO_ID = os.getenv("LOTUS_RISK_LIVE_PORTFOLIO_ID", "PB_SG_GLOBAL_BAL_001")
AS_OF_DATE = os.getenv("LOTUS_RISK_LIVE_AS_OF_DATE", "2026-03-31")


def _wealth_drawdown(return_series: Sequence[float]) -> list[float]:
    wealth = 1.0
    running_peak: float | None = None
    drawdowns: list[float] = []
    for daily_return in return_series:
        wealth *= 1.0 + daily_return
        running_peak = wealth if running_peak is None else max(running_peak, wealth)
        drawdowns.append(wealth / running_peak - 1.0)
    return drawdowns


def _max_drawdown(drawdowns: Sequence[float]) -> float:
    return min(drawdowns) if drawdowns else 0.0


def _ulcer_index(drawdowns: Sequence[float]) -> float:
    if not drawdowns:
        return 0.0
    return math.sqrt(sum(value * value for value in drawdowns) / len(drawdowns))


def _time_under_water(drawdowns: Sequence[float]) -> int:
    return sum(1 for value in drawdowns if value < 0.0)


def test_live_stateful_drawdown_reconciles_with_upstream_returns() -> None:
    returns_payload = {
        "portfolio_id": PORTFOLIO_ID,
        "as_of_date": AS_OF_DATE,
        "window": {"mode": "RELATIVE", "period": "YTD"},
        "frequency": "DAILY",
        "metric_basis": "NET",
        "reporting_currency": None,
        "series_selection": {
            "include_portfolio": True,
            "include_benchmark": True,
            "include_risk_free": False,
        },
        "data_policy": {
            "missing_data_policy": "FAIL_FAST",
            "fill_method": "NONE",
            "calendar_policy": "BUSINESS",
        },
        "input_mode": "stateful",
        "stateful_input": {},
    }
    drawdown_payload = {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE,
            "periods": [{"type": "YTD", "name": "YTD"}],
            "benchmark_policy": {
                "include_benchmark": True,
                "missing_benchmark_policy": "REQUIRE",
            },
        },
        "analysis_options": {
            "include_underwater_series": True,
            "include_episode_list": True,
            "top_n_episodes": 3,
            "cdar_alpha": 0.95,
            "minimum_episode_depth_bps": 0.0,
            "duration_unit": "BUSINESS_DAYS",
        },
    }

    upstream_body = fetch_live_returns_series(
        base_url=PERFORMANCE_BASE_URL,
        request_payload=returns_payload,
    )
    with httpx.Client(timeout=30.0) as client:
        drawdown_response = client.post(f"{RISK_BASE_URL}/analytics/risk/drawdown", json=drawdown_payload)
        drawdown_response.raise_for_status()
    drawdown_body = drawdown_response.json()

    series = upstream_body["series"]
    portfolio_returns = extract_decimal_returns(series["portfolio_returns"])
    benchmark_returns = extract_decimal_returns(series["benchmark_returns"])
    assert portfolio_returns, "expected live upstream portfolio returns"
    assert benchmark_returns, "expected live upstream benchmark returns"

    portfolio_drawdowns = _wealth_drawdown([value for _, value in portfolio_returns])
    benchmark_by_date = {date_value: value for date_value, value in benchmark_returns}
    active_returns = [
        portfolio_value - benchmark_by_date[date_value]
        for date_value, portfolio_value in portfolio_returns
        if date_value in benchmark_by_date
    ]
    active_drawdowns = _wealth_drawdown(active_returns)

    period = drawdown_body["results"]["YTD"]
    summary = period["summary"]
    relative = period["relative_to_benchmark"]

    assert summary["max_drawdown"] == pytest.approx(_max_drawdown(portfolio_drawdowns), abs=1e-12)
    assert summary["ulcer_index"] == pytest.approx(_ulcer_index(portfolio_drawdowns), abs=1e-12)
    assert summary["time_under_water_days"] == _time_under_water(portfolio_drawdowns)
    assert relative["max_drawdown"] == pytest.approx(_max_drawdown(active_drawdowns), abs=1e-12)
    assert relative["time_under_water_days"] == _time_under_water(active_drawdowns)
    assert drawdown_body["metadata"]["include_benchmark"] is True
    assert drawdown_body["metadata"]["include_underwater_series"] is True
