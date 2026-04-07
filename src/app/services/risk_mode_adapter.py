from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.contracts.risk import (
    ReturnPoint,
    RiskRequestScope,
    RiskResponse,
    RiskStatelessCalculationInput,
    StatefulRiskInput,
)
from app.services.risk_engine import calculate_risk
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import (
    extract_required_portfolio_returns,
    to_return_points,
)


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


_BENCHMARK_METRICS = {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}


def _portfolio_open_date(series_points: list[ReturnPoint], *, as_of_date: date) -> date:
    if not series_points:
        return as_of_date
    return min(point.date for point in series_points)


def _build_stateful_source_request(stateful: StatefulRiskInput) -> dict[str, Any]:
    include_benchmark = any(metric in _BENCHMARK_METRICS for metric in stateful.metrics)
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency=stateful.options.frequency,
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=include_benchmark,
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )


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
    series, portfolio_points = extract_required_portfolio_returns(source_response)

    benchmark_points: list[ReturnPoint] = []
    if any(metric in _BENCHMARK_METRICS for metric in stateful.metrics):
        benchmark_points = to_return_points(series.get("benchmark_returns"))

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
