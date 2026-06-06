from __future__ import annotations

from datetime import date
from typing import Any, Literal

from app.contracts.risk import RiskRequestPeriod
from app.services.source_window import build_returns_series_window


def _series_selection_payload(
    *,
    include_benchmark: bool,
    include_risk_free: bool,
) -> dict[str, bool]:
    return {
        "include_portfolio": True,
        "include_benchmark": include_benchmark,
        "include_risk_free": include_risk_free,
    }


def _data_policy_payload(
    missing_data_policy: Literal["ALLOW_PARTIAL", "FAIL_FAST"],
) -> dict[str, str]:
    return {
        "missing_data_policy": missing_data_policy,
        "fill_method": "NONE",
        "calendar_policy": "BUSINESS",
    }


def build_stateful_returns_series_request(
    *,
    portfolio_id: str,
    as_of_date: date,
    periods: list[RiskRequestPeriod],
    frequency: str,
    metric_basis: Literal["NET", "GROSS"],
    reporting_currency: str | None,
    include_benchmark: bool,
    include_risk_free: bool,
    missing_data_policy: Literal["ALLOW_PARTIAL", "FAIL_FAST"],
    benchmark_id: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "portfolio_id": portfolio_id,
        "as_of_date": as_of_date.isoformat(),
        "window": build_returns_series_window(
            periods=periods,
            as_of_date=as_of_date,
        ),
        "frequency": frequency,
        "metric_basis": metric_basis,
        "reporting_currency": reporting_currency,
        "series_selection": _series_selection_payload(
            include_benchmark=include_benchmark,
            include_risk_free=include_risk_free,
        ),
        "data_policy": _data_policy_payload(missing_data_policy),
        "input_mode": "stateful",
        "stateful_input": {},
    }
    if include_benchmark and benchmark_id:
        request["benchmark"] = {
            "benchmark_id": benchmark_id,
            "return_source": "calculated",
        }
    return request
