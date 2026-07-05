from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.contracts.risk import (
    ReturnPoint,
    RiskOptions,
    RiskRequestScope,
    RiskResponse,
    RiskStatelessCalculationInput,
    StatefulRiskInput,
)
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint
from app.services.core_risk_free_series import (
    build_risk_free_series_request,
    to_risk_free_return_points,
)
from app.services.risk_engine import calculate_risk
from app.services.risk import helpers as risk_helpers
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


class LotusCoreClientProtocol(Protocol):
    async def get_risk_free_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


_BENCHMARK_METRICS = risk_helpers.BENCHMARK_METRICS
_RISK_FREE_METRICS = risk_helpers.RISK_METRICS_REQUIRING_RISK_FREE


@dataclass(frozen=True)
class _StatefulRiskSource:
    source_payload: dict[str, Any]
    risk_free_request: dict[str, Any] | None
    portfolio_points: list[ReturnPoint]
    benchmark_points: list[ReturnPoint]
    risk_free_points: list[ReturnPoint]


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
        benchmark_id=stateful.benchmark_id,
        include_risk_free=False,
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


def _requires_benchmark(stateful: StatefulRiskInput) -> bool:
    return any(metric in _BENCHMARK_METRICS for metric in stateful.metrics)


def _requires_risk_free(stateful: StatefulRiskInput) -> bool:
    return any(metric in _RISK_FREE_METRICS for metric in stateful.metrics)


def _annualization_factor(options: RiskOptions) -> int:
    return (
        options.annualization_factor
        or {
            "DAILY": 252,
            "WEEKLY": 52,
            "MONTHLY": 12,
        }[options.frequency]
    )


def _explicit_window_bounds(source_payload: dict[str, Any]) -> tuple[date, date]:
    window = source_payload.get("window")
    if not isinstance(window, dict) or window.get("mode") != "EXPLICIT":
        raise ValueError(
            "explicit return window is required for stateful Sharpe risk-free sourcing"
        )
    raw_start = window.get("from_date")
    raw_end = window.get("to_date")
    if not isinstance(raw_start, str) or not isinstance(raw_end, str):
        raise ValueError("explicit return window bounds are required for risk-free sourcing")
    return date.fromisoformat(raw_start), date.fromisoformat(raw_end)


def _build_stateful_risk_free_request(
    *,
    stateful: StatefulRiskInput,
    source_payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not _requires_risk_free(stateful):
        return None
    if stateful.reporting_currency is None:
        raise ValueError("reporting_currency is required for stateful Sharpe risk-free sourcing")
    start_date, end_date = _explicit_window_bounds(source_payload)
    return build_risk_free_series_request(
        currency=stateful.reporting_currency,
        as_of_date=stateful.as_of_date,
        start_date=start_date,
        end_date=end_date,
    )


async def _fetch_stateful_source_payloads(
    *,
    source_payload: dict[str, Any],
    risk_free_request: dict[str, Any] | None,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if risk_free_request is not None:
        if core_client is None:
            raise ValueError("lotus-core client is required for stateful Sharpe risk-free sourcing")
        source_response, risk_free_response = await asyncio.gather(
            performance_client.get_returns_series(
                request_payload=source_payload,
                correlation_id=correlation_id,
            ),
            core_client.get_risk_free_series(
                request_payload=risk_free_request,
                correlation_id=correlation_id,
            ),
        )
        return source_response, risk_free_response

    source_response = await performance_client.get_returns_series(
        request_payload=source_payload,
        correlation_id=correlation_id,
    )
    return source_response, None


async def _fetch_stateful_risk_source(
    *,
    stateful: StatefulRiskInput,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> _StatefulRiskSource:
    source_payload = _build_stateful_source_request(stateful)
    risk_free_request = _build_stateful_risk_free_request(
        stateful=stateful,
        source_payload=source_payload,
    )
    source_response, risk_free_response = await _fetch_stateful_source_payloads(
        source_payload=source_payload,
        risk_free_request=risk_free_request,
        performance_client=performance_client,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    series, portfolio_points = extract_required_portfolio_returns(source_response)

    benchmark_points: list[ReturnPoint] = []
    if _requires_benchmark(stateful):
        benchmark_points = to_return_points(series.get("benchmark_returns"))

    risk_free_points: list[ReturnPoint] = []
    if risk_free_request is not None and risk_free_response is not None:
        risk_free_points = to_risk_free_return_points(
            risk_free_response,
            annualization_basis=_annualization_factor(stateful.options),
        )
        if not risk_free_points:
            raise missing_upstream_data(
                service="lotus-core",
                operation="/integration/reference/risk-free-series",
                message="lotus-core returned no usable risk-free returns for stateful Sharpe",
            )

    return _StatefulRiskSource(
        source_payload=source_payload,
        risk_free_request=risk_free_request,
        portfolio_points=portfolio_points,
        benchmark_points=benchmark_points,
        risk_free_points=risk_free_points,
    )


def _options_with_sourced_risk_free(
    *,
    options: RiskOptions,
    risk_free_points: list[ReturnPoint],
) -> RiskOptions:
    risk_free_annual_rate = _annualized_rate_from_risk_free_returns(
        risk_free_points,
        annualization_factor=_annualization_factor(options),
    )
    if risk_free_annual_rate is None:
        return options
    return options.model_copy(
        update={
            "risk_free_mode": "ANNUAL_RATE",
            "risk_free_annual_rate": risk_free_annual_rate,
        }
    )


def _build_stateful_stateless_risk_input(
    *,
    stateful: StatefulRiskInput,
    source: _StatefulRiskSource,
) -> RiskStatelessCalculationInput:
    options = _options_with_sourced_risk_free(
        options=stateful.options,
        risk_free_points=source.risk_free_points,
    )
    return RiskStatelessCalculationInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        metrics=stateful.metrics,
        options=options,
        portfolio_open_date=_portfolio_open_date(
            source.portfolio_points,
            as_of_date=stateful.as_of_date,
        ),
        returns=source.portfolio_points,
        benchmark_returns=source.benchmark_points,
    )


def _attach_stateful_risk_lineage(
    *,
    response: RiskResponse,
    source: _StatefulRiskSource,
) -> RiskResponse:
    response.metadata.source_services = ordered_source_services(
        "lotus-performance",
        *(("lotus-core",) if source.risk_free_request is not None else ()),
    )
    response.metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=source.source_payload,
    )
    if source.risk_free_request is not None:
        response.metadata.upstream_request_fingerprints.update(
            upstream_request_fingerprint(
                service="lotus-core",
                operation="/integration/reference/risk-free-series",
                payload=source.risk_free_request,
            )
        )
    return response


async def calculate_risk_stateful(
    stateful: StatefulRiskInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None = None,
    correlation_id: str | None,
) -> RiskResponse:
    source = await _fetch_stateful_risk_source(
        stateful=stateful,
        performance_client=performance_client,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    response = calculate_risk(
        _build_stateful_stateless_risk_input(
            stateful=stateful,
            source=source,
        )
    )
    return _attach_stateful_risk_lineage(
        response=response,
        source=source,
    )
