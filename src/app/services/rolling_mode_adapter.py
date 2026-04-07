from __future__ import annotations

from typing import Any, Protocol

from app.contracts.risk import RiskRequestScope
from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingInputMode,
    RollingResponse,
    RollingStatefulInput,
    RollingStatelessInput,
)
from app.services.rolling_engine import ROLLING_SHARPE_METRIC, calculate_rolling_metrics
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


class LotusCoreClientProtocol(Protocol):
    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def _build_stateful_source_request(stateful: RollingStatefulInput) -> dict[str, Any]:
    include_benchmark = any(
        metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics
    )
    include_risk_free = ROLLING_SHARPE_METRIC in stateful.rolling_options.metrics
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=include_benchmark,
        include_risk_free=include_risk_free,
        missing_data_policy="ALLOW_PARTIAL",
    )


async def _resolve_reporting_currency(
    *,
    stateful: RollingStatefulInput,
    include_risk_free: bool,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> str | None:
    if stateful.reporting_currency:
        return stateful.reporting_currency
    if not include_risk_free:
        return None
    if core_client is None:
        raise ValueError(
            "reporting_currency is required for rolling Sharpe in stateful mode when lotus-core is unavailable"
        )

    snapshot = await core_client.get_core_snapshot(
        portfolio_id=stateful.portfolio_id,
        request_payload={
            "snapshot_mode": "BASELINE",
            "as_of_date": stateful.as_of_date.isoformat(),
            "sections": ["portfolio_totals"],
        },
        correlation_id=correlation_id,
    )
    valuation_context = snapshot.get("valuation_context")
    if not isinstance(valuation_context, dict):
        raise ValueError("lotus-core core-snapshot payload missing valuation_context")
    resolved_reporting_currency = valuation_context.get("reporting_currency")
    if not isinstance(resolved_reporting_currency, str) or not resolved_reporting_currency:
        resolved_reporting_currency = valuation_context.get("portfolio_currency")
    if not isinstance(resolved_reporting_currency, str) or not resolved_reporting_currency:
        raise ValueError(
            "lotus-core core-snapshot payload missing portfolio/reporting currency required for rolling Sharpe"
        )
    return resolved_reporting_currency


async def calculate_rolling_metrics_stateful(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None = None,
    correlation_id: str | None,
) -> RollingResponse:
    include_risk_free = ROLLING_SHARPE_METRIC in stateful.rolling_options.metrics
    resolved_reporting_currency = await _resolve_reporting_currency(
        stateful=stateful,
        include_risk_free=include_risk_free,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    if resolved_reporting_currency != stateful.reporting_currency:
        stateful = stateful.model_copy(update={"reporting_currency": resolved_reporting_currency})

    source_payload = _build_stateful_source_request(stateful)
    source_response = await performance_client.get_returns_series(
        request_payload=source_payload,
        correlation_id=correlation_id,
    )
    series, portfolio_points = extract_required_portfolio_returns(source_response)

    include_benchmark = any(
        metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics
    )
    benchmark_points = to_return_points(series.get("benchmark_returns"))
    if include_benchmark and not benchmark_points:
        raise ValueError(
            "lotus-performance returns-series returned no benchmark returns for requested rolling benchmark metrics"
        )

    risk_free_points = to_return_points(series.get("risk_free_returns"))
    if include_risk_free and not risk_free_points:
        raise ValueError(
            "lotus-performance returns-series returned no risk-free returns for requested rolling Sharpe"
        )

    stateless = RollingStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=portfolio_points,
        benchmark_returns=benchmark_points,
        risk_free_returns=risk_free_points,
        rolling_options=stateful.rolling_options,
    )
    return calculate_rolling_metrics(stateless, input_mode=RollingInputMode.STATEFUL)

