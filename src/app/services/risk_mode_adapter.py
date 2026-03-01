from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.risk import (
    ReturnPoint,
    RiskRequestScope,
    RiskResponse,
    RiskStatelessCalculationInput,
    StatefulRiskInput,
)
from app.services.risk_engine import calculate_risk


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


_BENCHMARK_METRICS = {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}


def _decimal_return_to_percentage_points(value: Any) -> float:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid return value from lotus-performance: {value}") from exc
    return float(decimal_value * Decimal("100"))


def _to_return_points(series: Any) -> list[ReturnPoint]:
    if not isinstance(series, list):
        return []
    result: list[ReturnPoint] = []
    for row in series:
        if not isinstance(row, dict):
            continue
        raw_date = row.get("date")
        if not isinstance(raw_date, str):
            continue
        result.append(
            ReturnPoint(
                date=date.fromisoformat(raw_date),
                value=_decimal_return_to_percentage_points(row.get("return_value")),
            )
        )
    return result


def _portfolio_open_date(series_points: list[ReturnPoint], *, as_of_date: date) -> date:
    if not series_points:
        return as_of_date
    return min(point.date for point in series_points)


def _build_stateful_source_request(stateful: StatefulRiskInput) -> dict[str, Any]:
    # Stateful risk currently uses canonical core-backed series path through lotus-performance.
    return {
        "portfolio_id": stateful.portfolio_id,
        "as_of_date": stateful.as_of_date.isoformat(),
        "window": {"mode": "RELATIVE", "period": "SI"},
        "frequency": stateful.options.frequency,
        "metric_basis": stateful.net_or_gross,
        "reporting_currency": stateful.reporting_currency,
        "series_selection": {
            "include_portfolio": True,
            "include_benchmark": False,
            "include_risk_free": False,
        },
        "data_policy": {
            "missing_data_policy": "ALLOW_PARTIAL",
            "fill_method": "NONE",
            "calendar_policy": "BUSINESS",
        },
        "source": {"input_mode": "core_api_ref"},
    }


async def calculate_risk_stateful(
    stateful: StatefulRiskInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    correlation_id: str | None,
) -> RiskResponse:
    source_payload = _build_stateful_source_request(stateful)
    source_response = await performance_client.get_returns_series(
        request_payload=source_payload,
        correlation_id=correlation_id,
    )
    series = source_response.get("series")
    if not isinstance(series, dict):
        raise ValueError("lotus-performance returns-series payload missing 'series' object")

    portfolio_points = _to_return_points(series.get("portfolio_returns"))
    if not portfolio_points:
        raise ValueError("lotus-performance returns-series returned no portfolio returns")

    benchmark_points: list[ReturnPoint] = []
    if any(metric in _BENCHMARK_METRICS for metric in stateful.metrics):
        benchmark_points = _to_return_points(series.get("benchmark_returns"))

    stateless_request = RiskStatelessCalculationInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        metrics=stateful.metrics,
        options=stateful.options,
        portfolio_open_date=_portfolio_open_date(portfolio_points, as_of_date=stateful.as_of_date),
        returns=portfolio_points,
        benchmark_returns=benchmark_points,
    )
    return calculate_risk(stateless_request)
