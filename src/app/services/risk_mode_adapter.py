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
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint
from app.services.risk_engine import calculate_risk
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import (
    extract_required_portfolio_returns,
    to_return_points,
)
from app.upstream_errors import missing_upstream_data


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


_BENCHMARK_METRICS = {"BETA", "TRACKING_ERROR", "INFORMATION_RATIO"}
_RISK_FREE_METRICS = {"SHARPE"}


def _portfolio_open_date(series_points: list[ReturnPoint], *, as_of_date: date) -> date:
    if not series_points:
        return as_of_date
    return min(point.date for point in series_points)


def _build_stateful_source_request(stateful: StatefulRiskInput) -> dict[str, Any]:
    include_benchmark = any(metric in _BENCHMARK_METRICS for metric in stateful.metrics)
    include_risk_free = any(metric in _RISK_FREE_METRICS for metric in stateful.metrics)
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency=stateful.options.frequency,
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=include_benchmark,
        include_risk_free=include_risk_free,
        missing_data_policy="ALLOW_PARTIAL",
    )


def _annualized_rate_from_risk_free_returns(
    risk_free_points: list[ReturnPoint],
    *,
    annualization_factor: int,
) -> float | None:
    if not risk_free_points:
        return None
    mean_periodic_rate = sum(point.value / 100 for point in risk_free_points) / len(
        risk_free_points
    )
    return (1.0 + mean_periodic_rate) ** annualization_factor - 1.0


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

    risk_free_points: list[ReturnPoint] = []
    if any(metric in _RISK_FREE_METRICS for metric in stateful.metrics):
        risk_free_points = to_return_points(series.get("risk_free_returns"))
        if not risk_free_points:
            raise missing_upstream_data(
                service="lotus-performance",
                operation="/integration/returns/series",
                message=(
                    "lotus-performance returns-series returned no sourced risk-free returns "
                    "for stateful Sharpe"
                ),
            )

    options = stateful.options
    risk_free_annual_rate = _annualized_rate_from_risk_free_returns(
        risk_free_points,
        annualization_factor=options.annualization_factor
        or {
            "DAILY": 252,
            "WEEKLY": 52,
            "MONTHLY": 12,
        }[options.frequency],
    )
    if risk_free_annual_rate is not None:
        options = options.model_copy(
            update={
                "risk_free_mode": "ANNUAL_RATE",
                "risk_free_annual_rate": risk_free_annual_rate,
            }
        )

    stateless_request = RiskStatelessCalculationInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        metrics=stateful.metrics,
        options=options,
        portfolio_open_date=_portfolio_open_date(portfolio_points, as_of_date=stateful.as_of_date),
        returns=portfolio_points,
        benchmark_returns=benchmark_points,
    )
    response = calculate_risk(stateless_request)
    response.metadata.source_services = ordered_source_services(
        "lotus-performance",
        *(("lotus-core",) if risk_free_points else ()),
    )
    response.metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=source_payload,
    )
    return response
