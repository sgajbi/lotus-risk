from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.contracts.downstream_authority import DownstreamAuthority
from app.contracts.risk import (
    ReturnPoint,
    RiskOptions,
    RiskRequestScope,
    RiskResponse,
    RiskStatelessCalculationInput,
    StatefulRiskInput,
)
from app.contracts.stateful_returns_source_evidence import StatefulReturnsSourceEvidence
from app.integrations.upstream_operations import LOTUS_CORE_SNAPSHOT_OPERATION
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint
from app.services.core_portfolio_currency import resolve_portfolio_reporting_currency
from app.services.core_risk_free_series import (
    build_risk_free_series_request,
    to_risk_free_return_points,
)
from app.services.risk import helpers as risk_helpers
from app.services.risk.calculation_orchestrator import annualization_factor_for_options
from app.services.risk_engine import calculate_risk
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import (
    extract_required_portfolio_returns,
    extract_stateful_returns_source_evidence,
    normalize_return_points_to_resolved_window,
    to_return_points,
)
from app.upstream_errors import missing_upstream_data


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...


class LotusCoreClientProtocol(Protocol):
    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...

    async def get_risk_free_series(
        self,
        *,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...


_BENCHMARK_METRICS = risk_helpers.BENCHMARK_METRICS


@dataclass(frozen=True)
class _StatefulRiskSource:
    source_payload: dict[str, Any]
    core_snapshot_request: dict[str, Any] | None
    risk_free_request: dict[str, Any] | None
    reporting_currency: str | None
    portfolio_points: list[ReturnPoint]
    benchmark_points: list[ReturnPoint]
    risk_free_points: list[ReturnPoint]
    evidence: StatefulReturnsSourceEvidence


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
    return risk_helpers.requires_risk_free(stateful.metrics)


def _risk_free_window_bounds(portfolio_points: list[ReturnPoint]) -> tuple[date, date]:
    dates = [point.date for point in portfolio_points]
    return min(dates), max(dates)


def _build_stateful_risk_free_request(
    *,
    stateful: StatefulRiskInput,
    portfolio_points: list[ReturnPoint],
) -> dict[str, Any] | None:
    if not _requires_risk_free(stateful):
        return None
    if stateful.reporting_currency is None:
        raise ValueError("reporting currency is required for stateful risk-free sourcing")
    start_date, end_date = _risk_free_window_bounds(portfolio_points)
    return build_risk_free_series_request(
        currency=stateful.reporting_currency,
        as_of_date=stateful.as_of_date,
        start_date=start_date,
        end_date=end_date,
    )


async def _fetch_stateful_source_payload(
    *,
    source_payload: dict[str, Any],
    performance_client: LotusPerformanceClientProtocol,
    authority: DownstreamAuthority,
) -> dict[str, Any]:
    return await performance_client.get_returns_series(
        request_payload=source_payload,
        authority=authority,
    )


async def _fetch_risk_free_payload(
    *,
    risk_free_request: dict[str, Any] | None,
    core_client: LotusCoreClientProtocol | None,
    authority: DownstreamAuthority,
) -> dict[str, Any] | None:
    if risk_free_request is None:
        return None
    if core_client is None:
        raise ValueError("lotus-core client is required for stateful Sharpe risk-free sourcing")
    return await core_client.get_risk_free_series(
        request_payload=risk_free_request,
        authority=authority,
    )


async def _fetch_stateful_risk_source(
    *,
    stateful: StatefulRiskInput,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    core_snapshot_request: dict[str, Any] | None,
    authority: DownstreamAuthority,
) -> _StatefulRiskSource:
    source_payload = _build_stateful_source_request(stateful)
    source_response = await _fetch_stateful_source_payload(
        source_payload=source_payload,
        performance_client=performance_client,
        authority=authority,
    )
    series, portfolio_points = extract_required_portfolio_returns(
        source_response,
        frequency=stateful.options.frequency,
    )
    evidence = extract_stateful_returns_source_evidence(
        source_response,
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        frequency=stateful.options.frequency,
        metric_basis=stateful.net_or_gross,
        requested_window=source_payload["window"],
        returned_points=portfolio_points,
    )
    portfolio_points = normalize_return_points_to_resolved_window(
        source_response,
        portfolio_points,
        frequency=stateful.options.frequency,
    )
    risk_free_request = _build_stateful_risk_free_request(
        stateful=stateful,
        portfolio_points=portfolio_points,
    )
    # Reference facts are global, but Core still admits the caller's tenant context.
    risk_free_response = await _fetch_risk_free_payload(
        risk_free_request=risk_free_request,
        core_client=core_client,
        authority=authority,
    )

    benchmark_points: list[ReturnPoint] = []
    if _requires_benchmark(stateful):
        benchmark_points = to_return_points(
            series.get("benchmark_returns"),
            frequency=stateful.options.frequency,
        )
        benchmark_points = normalize_return_points_to_resolved_window(
            source_response,
            benchmark_points,
            frequency=stateful.options.frequency,
        )

    risk_free_points: list[ReturnPoint] = []
    if risk_free_request is not None and risk_free_response is not None:
        risk_free_points = to_risk_free_return_points(
            risk_free_response,
            annualization_basis=annualization_factor_for_options(stateful.options),
        )
        if not risk_free_points:
            raise missing_upstream_data(
                service="lotus-core",
                operation="/integration/reference/risk-free-series",
                message="lotus-core returned no usable risk-free returns for stateful Sharpe",
            )

    return _StatefulRiskSource(
        source_payload=source_payload,
        core_snapshot_request=core_snapshot_request,
        risk_free_request=risk_free_request,
        reporting_currency=stateful.reporting_currency,
        portfolio_points=portfolio_points,
        benchmark_points=benchmark_points,
        risk_free_points=risk_free_points,
        evidence=evidence,
    )


def _options_with_sourced_risk_free(
    *,
    options: RiskOptions,
    risk_free_points: list[ReturnPoint],
) -> RiskOptions:
    risk_free_annual_rate = _annualized_rate_from_risk_free_returns(
        risk_free_points,
        annualization_factor=annualization_factor_for_options(options),
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
            reporting_currency=source.reporting_currency,
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
    portfolio_id: str,
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
    if source.core_snapshot_request is not None:
        response.metadata.upstream_request_fingerprints.update(
            upstream_request_fingerprint(
                service="lotus-core",
                operation=LOTUS_CORE_SNAPSHOT_OPERATION,
                payload={
                    "portfolio_id": portfolio_id,
                    "request_payload": source.core_snapshot_request,
                },
            )
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
    authority: DownstreamAuthority,
) -> RiskResponse:
    resolved_currency = await resolve_portfolio_reporting_currency(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        requested_currency=stateful.reporting_currency,
        requires_risk_free=_requires_risk_free(stateful),
        core_client=core_client,
        authority=authority,
    )
    if resolved_currency.reporting_currency != stateful.reporting_currency:
        stateful = stateful.model_copy(
            update={"reporting_currency": resolved_currency.reporting_currency}
        )
    source = await _fetch_stateful_risk_source(
        stateful=stateful,
        performance_client=performance_client,
        core_client=core_client,
        core_snapshot_request=resolved_currency.snapshot_request,
        authority=authority,
    )
    response = calculate_risk(
        _build_stateful_stateless_risk_input(
            stateful=stateful,
            source=source,
        ),
        source_returns_evidence=source.evidence,
    )
    return _attach_stateful_risk_lineage(
        response=response,
        source=source,
        portfolio_id=stateful.portfolio_id,
    )
