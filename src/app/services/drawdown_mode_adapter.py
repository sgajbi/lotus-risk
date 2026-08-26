from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownInputMode,
    DrawdownResponse,
    DrawdownStatefulInput,
    DrawdownStatelessInput,
)
from app.contracts.risk import ReturnPoint, RiskRequestScope
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint
from app.services.drawdown_engine import calculate_drawdown
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


@dataclass(frozen=True)
class _DrawdownSourceSeries:
    portfolio_points: list[ReturnPoint]
    benchmark_points: list[ReturnPoint]


def _build_stateful_source_request(
    stateful: DrawdownStatefulInput,
    *,
    analysis_options: DrawdownAnalysisOptions,
) -> dict[str, Any]:
    # keep options local to lotus-risk; returns-series only needs sourcing controls
    _ = analysis_options
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=stateful.benchmark_policy.include_benchmark,
        benchmark_id=stateful.benchmark_id,
        include_risk_free=False,
        missing_data_policy=(
            "FAIL_FAST"
            if stateful.benchmark_policy.missing_benchmark_policy == "REQUIRE"
            else "ALLOW_PARTIAL"
        ),
    )


def _parse_drawdown_source_series(
    source_response: dict[str, Any],
    *,
    stateful: DrawdownStatefulInput,
) -> _DrawdownSourceSeries:
    series, portfolio_points = extract_required_portfolio_returns(source_response)
    benchmark_points = to_return_points(series.get("benchmark_returns"))
    if (
        stateful.benchmark_policy.include_benchmark
        and not benchmark_points
        and stateful.benchmark_policy.missing_benchmark_policy == "REQUIRE"
    ):
        raise ValueError(
            "lotus-performance returns-series returned no benchmark returns while benchmark was required"
        )
    return _DrawdownSourceSeries(
        portfolio_points=portfolio_points,
        benchmark_points=benchmark_points,
    )


def _drawdown_stateless_request(
    stateful: DrawdownStatefulInput,
    source_series: _DrawdownSourceSeries,
) -> DrawdownStatelessInput:
    return DrawdownStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=source_series.portfolio_points,
        benchmark_returns=source_series.benchmark_points,
    )


async def calculate_drawdown_stateful(
    stateful: DrawdownStatefulInput,
    *,
    analysis_options: DrawdownAnalysisOptions,
    performance_client: LotusPerformanceClientProtocol,
    correlation_id: str | None,
) -> DrawdownResponse:
    source_payload = _build_stateful_source_request(stateful, analysis_options=analysis_options)
    source_response = await performance_client.get_returns_series(
        request_payload=source_payload,
        correlation_id=correlation_id,
    )
    source_series = _parse_drawdown_source_series(
        source_response,
        stateful=stateful,
    )
    stateless = _drawdown_stateless_request(stateful, source_series)
    response = calculate_drawdown(
        stateless,
        input_mode=DrawdownInputMode.STATEFUL,
        analysis_options=analysis_options,
        include_benchmark=stateful.benchmark_policy.include_benchmark,
        missing_benchmark_policy=stateful.benchmark_policy.missing_benchmark_policy,
    )
    response.metadata.source_services = ordered_source_services("lotus-performance")
    response.metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=source_payload,
    )
    return response
