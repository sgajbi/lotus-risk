from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownInputMode,
    DrawdownResponse,
    DrawdownStatefulInput,
    DrawdownStatelessInput,
)
from app.contracts.risk import ReturnPoint, RiskRequestScope
from app.services.drawdown_engine import calculate_drawdown
from app.services.source_window import build_returns_series_window


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


def _build_stateful_source_request(
    stateful: DrawdownStatefulInput,
    *,
    analysis_options: DrawdownAnalysisOptions,
) -> dict[str, Any]:
    # keep options local to lotus-risk; returns-series only needs sourcing controls
    _ = analysis_options
    return {
        "portfolio_id": stateful.portfolio_id,
        "as_of_date": stateful.as_of_date.isoformat(),
        "window": build_returns_series_window(
            periods=stateful.periods,
            as_of_date=stateful.as_of_date,
        ),
        "frequency": "DAILY",
        "metric_basis": stateful.net_or_gross,
        "reporting_currency": stateful.reporting_currency,
        "series_selection": {
            "include_portfolio": True,
            "include_benchmark": stateful.benchmark_policy.include_benchmark,
            "include_risk_free": False,
        },
        "data_policy": {
            "missing_data_policy": (
                "FAIL_FAST"
                if stateful.benchmark_policy.missing_benchmark_policy == "REQUIRE"
                else "ALLOW_PARTIAL"
            ),
            "fill_method": "NONE",
            "calendar_policy": "BUSINESS",
        },
        "input_mode": "stateful",
        "stateful_input": {},
    }


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
    series = source_response.get("series")
    if not isinstance(series, dict):
        raise ValueError("lotus-performance returns-series payload missing 'series' object")

    portfolio_points = _to_return_points(series.get("portfolio_returns"))
    if not portfolio_points:
        raise ValueError("lotus-performance returns-series returned no portfolio returns")
    benchmark_points = _to_return_points(series.get("benchmark_returns"))
    if stateful.benchmark_policy.include_benchmark and not benchmark_points:
        if stateful.benchmark_policy.missing_benchmark_policy == "REQUIRE":
            raise ValueError(
                "lotus-performance returns-series returned no benchmark returns while benchmark was required"
            )

    stateless = DrawdownStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=portfolio_points,
        benchmark_returns=benchmark_points,
    )
    return calculate_drawdown(
        stateless,
        input_mode=DrawdownInputMode.STATEFUL,
        analysis_options=analysis_options,
    )

