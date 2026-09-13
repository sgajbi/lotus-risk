from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.contracts.attribution import HistoricalAttributionStatefulInput
from app.contracts.attribution_common_inputs import (
    requires_active_attribution as _requires_active_attribution,
)
from app.contracts.downstream_authority import DownstreamAuthority
from app.contracts.risk import ReturnPoint
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import (
    extract_required_portfolio_returns,
    to_return_points,
)
from app.upstream_errors import missing_upstream_data


class LotusPerformanceReturnsClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class StatefulReturnsContext:
    returns_request: dict[str, Any]
    portfolio_returns: list[ReturnPoint]
    benchmark_returns: list[ReturnPoint]
    start_date: date


def requires_active_attribution(stateful: HistoricalAttributionStatefulInput) -> bool:
    """Delegates to the single contract-owned predicate so the sourcing flag, request
    validation, and the calculation-time benchmark gate share one rule."""
    return _requires_active_attribution(stateful.attribution_options)


def build_stateful_returns_request(stateful: HistoricalAttributionStatefulInput) -> dict[str, Any]:
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=requires_active_attribution(stateful),
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )


async def fetch_stateful_returns_context(
    *,
    stateful: HistoricalAttributionStatefulInput,
    performance_client: LotusPerformanceReturnsClientProtocol,
    authority: DownstreamAuthority,
) -> StatefulReturnsContext:
    returns_request = build_stateful_returns_request(stateful)
    returns_response = await performance_client.get_returns_series(
        request_payload=returns_request,
        authority=authority,
    )
    series, portfolio_returns = extract_required_portfolio_returns(returns_response)
    benchmark_returns = to_return_points(series.get("benchmark_returns"))
    if requires_active_attribution(stateful) and not benchmark_returns:
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=(
                "lotus-performance returns-series returned no benchmark returns for "
                "requested stateful active-risk attribution"
            ),
        )
    return StatefulReturnsContext(
        returns_request=returns_request,
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        start_date=min(point.date for point in portfolio_returns),
    )


__all__ = [
    "LotusPerformanceReturnsClientProtocol",
    "StatefulReturnsContext",
    "build_stateful_returns_request",
    "fetch_stateful_returns_context",
    "requires_active_attribution",
]
