from __future__ import annotations

from typing import Any, Protocol

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownInputMode,
    DrawdownResponse,
    DrawdownStatefulInput,
    DrawdownStatelessInput,
)
from app.contracts.risk import RiskRequestScope
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
        include_risk_free=False,
        missing_data_policy=(
            "FAIL_FAST"
            if stateful.benchmark_policy.missing_benchmark_policy == "REQUIRE"
            else "ALLOW_PARTIAL"
        ),
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
    series, portfolio_points = extract_required_portfolio_returns(source_response)
    benchmark_points = to_return_points(series.get("benchmark_returns"))
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
        include_benchmark=stateful.benchmark_policy.include_benchmark,
        missing_benchmark_policy=stateful.benchmark_policy.missing_benchmark_policy,
    )
