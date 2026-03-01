from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.risk import ReturnPoint, RiskRequestScope
from app.contracts.rolling import (
    ROLLING_BENCHMARK_METRICS,
    RollingInputMode,
    RollingResponse,
    RollingStatefulInput,
    RollingStatelessInput,
)
from app.services.rolling_engine import ROLLING_SHARPE_METRIC, calculate_rolling_metrics


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


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


def _build_stateful_source_request(stateful: RollingStatefulInput) -> dict[str, Any]:
    include_benchmark = any(
        metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics
    )
    include_risk_free = ROLLING_SHARPE_METRIC in stateful.rolling_options.metrics
    return {
        "portfolio_id": stateful.portfolio_id,
        "as_of_date": stateful.as_of_date.isoformat(),
        "window": {"mode": "RELATIVE", "period": "SI"},
        "frequency": "DAILY",
        "metric_basis": stateful.net_or_gross,
        "reporting_currency": stateful.reporting_currency,
        "series_selection": {
            "include_portfolio": True,
            "include_benchmark": include_benchmark,
            "include_risk_free": include_risk_free,
        },
        "data_policy": {
            "missing_data_policy": "ALLOW_PARTIAL",
            "fill_method": "NONE",
            "calendar_policy": "BUSINESS",
        },
        "source": {"input_mode": "core_api_ref"},
    }


async def calculate_rolling_metrics_stateful(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    correlation_id: str | None,
) -> RollingResponse:
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

    include_benchmark = any(
        metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics
    )
    benchmark_points = _to_return_points(series.get("benchmark_returns"))
    if include_benchmark and not benchmark_points:
        raise ValueError(
            "lotus-performance returns-series returned no benchmark returns for requested rolling benchmark metrics"
        )

    include_risk_free = ROLLING_SHARPE_METRIC in stateful.rolling_options.metrics
    risk_free_points = _to_return_points(series.get("risk_free_returns"))
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
