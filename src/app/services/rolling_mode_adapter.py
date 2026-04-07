from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Protocol

from app.contracts.risk import RiskRequestScope
from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingInputMode,
    RollingResponse,
    RollingStatefulInput,
    RollingStatelessInput,
)
from app.services.core_risk_free_series import (
    build_risk_free_series_request,
    to_risk_free_return_points,
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

    async def get_risk_free_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def _build_stateful_source_request(stateful: RollingStatefulInput) -> dict[str, Any]:
    include_benchmark = any(
        metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics
    )
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=include_benchmark,
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )


def _explicit_window_bounds(source_payload: dict[str, Any]) -> tuple[date, date] | None:
    window = source_payload.get("window")
    if not isinstance(window, dict):
        return None
    if window.get("mode") != "EXPLICIT":
        return None

    raw_start = window.get("from_date")
    raw_end = window.get("to_date")
    if not isinstance(raw_start, str) or not isinstance(raw_end, str):
        return None
    return date.fromisoformat(raw_start), date.fromisoformat(raw_end)


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
    explicit_window = _explicit_window_bounds(source_payload)
    risk_free_response: dict[str, Any] | None = None

    if include_risk_free and core_client is None:
        raise ValueError(
            "lotus-core client is required for rolling Sharpe stateful risk-free sourcing"
        )

    if include_risk_free and explicit_window is not None:
        assert resolved_reporting_currency is not None
        checked_core_client = core_client
        assert checked_core_client is not None
        risk_free_request = build_risk_free_series_request(
            currency=resolved_reporting_currency,
            as_of_date=stateful.as_of_date,
            start_date=explicit_window[0],
            end_date=explicit_window[1],
        )
        source_response, risk_free_response = await asyncio.gather(
            performance_client.get_returns_series(
                request_payload=source_payload,
                correlation_id=correlation_id,
            ),
            checked_core_client.get_risk_free_series(
                request_payload=risk_free_request,
                correlation_id=correlation_id,
            ),
        )
    else:
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

    if include_risk_free and risk_free_response is None:
        assert core_client is not None
        assert resolved_reporting_currency is not None
        risk_free_request = build_risk_free_series_request(
            currency=resolved_reporting_currency,
            as_of_date=stateful.as_of_date,
            start_date=min(point.date for point in portfolio_points),
            end_date=max(point.date for point in portfolio_points),
        )
        risk_free_response = await core_client.get_risk_free_series(
            request_payload=risk_free_request,
            correlation_id=correlation_id,
        )

    risk_free_points = (
        to_risk_free_return_points(
            risk_free_response,
            annualization_basis=stateful.rolling_options.annualization_basis,
        )
        if include_risk_free and risk_free_response is not None
        else []
    )
    if include_risk_free and not risk_free_points:
        raise ValueError(
            "lotus-core risk-free-series returned no usable risk-free returns for requested rolling Sharpe"
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
