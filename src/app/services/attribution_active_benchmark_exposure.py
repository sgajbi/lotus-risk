from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.contracts.attribution import (
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionStatefulInput,
)
from app.contracts.risk import ReturnPoint
from app.services.benchmark_exposure_history import (
    BenchmarkExposureHistoryRequest,
    fetch_benchmark_exposure_history,
)
from app.upstream_errors import missing_upstream_data


class BenchmarkExposureClientProtocol(Protocol):
    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def validate_benchmark_exposure_alignment(
    *,
    benchmark_returns: list[ReturnPoint],
    benchmark_exposure_history: list[ExposurePoint],
) -> None:
    return_dates = {point.date for point in benchmark_returns}
    exposure_dates = {point.date for point in benchmark_exposure_history}
    missing_dates = sorted(return_dates - exposure_dates)
    if missing_dates:
        sample = ", ".join(date_value.isoformat() for date_value in missing_dates[:5])
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message=(
                "lotus-performance benchmark exposure context missing rows for benchmark "
                f"return dates: {sample}"
            ),
        )


async def fetch_active_benchmark_exposure_history(
    *,
    stateful: HistoricalAttributionStatefulInput,
    performance_client: BenchmarkExposureClientProtocol,
    benchmark_returns: list[ReturnPoint],
    start_date: date,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[ExposurePoint]:
    benchmark_exposure_history = await fetch_benchmark_exposure_history(
        BenchmarkExposureHistoryRequest(
            performance_client=performance_client,
            portfolio_id=stateful.portfolio_id,
            as_of_date=stateful.as_of_date,
            start_date=start_date,
            reporting_currency=stateful.reporting_currency,
            grouping_dimensions=grouping_dimensions,
            correlation_id=correlation_id,
        )
    )
    validate_benchmark_exposure_alignment(
        benchmark_returns=benchmark_returns,
        benchmark_exposure_history=benchmark_exposure_history,
    )
    return benchmark_exposure_history


__all__ = [
    "BenchmarkExposureClientProtocol",
    "fetch_active_benchmark_exposure_history",
    "validate_benchmark_exposure_alignment",
]
