from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.attribution import ExposurePoint, GroupingDimension
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data


class BenchmarkExposurePerformanceClientProtocol(Protocol):
    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def _as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message=f"Invalid benchmark exposure weight from lotus-performance: {value}",
        ) from exc


def _validate_lineage(response: dict[str, Any]) -> None:
    if response.get("source_service") != "lotus-performance":
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message=(
                "lotus-performance benchmark exposure context missing "
                "source_service=lotus-performance"
            ),
        )
    if response.get("contract_version") != "v1":
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message="lotus-performance benchmark exposure context missing contract_version=v1",
        )

    metadata = response.get("metadata")
    if not isinstance(metadata, dict):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message="lotus-performance benchmark exposure context payload missing metadata object",
        )
    if metadata.get("source_system") != "lotus-core":
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message="lotus-performance benchmark exposure context missing lotus-core lineage",
        )
    if metadata.get("served_by") != "lotus-performance":
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message=(
                "lotus-performance benchmark exposure context missing served_by=lotus-performance"
            ),
        )


def _build_request_payload(
    *,
    portfolio_id: str,
    as_of_date: date,
    start_date: date,
    reporting_currency: str | None,
    grouping_dimensions: list[GroupingDimension],
    page_token: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "portfolio_id": portfolio_id,
        "as_of_date": as_of_date.isoformat(),
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": as_of_date.isoformat(),
        },
        "frequency": "DAILY",
        "grouping_dimensions": grouping_dimensions,
        "page": {"page_size": 1000, "page_token": page_token},
    }
    if reporting_currency:
        payload["reporting_currency"] = reporting_currency
    return payload


def _rows_to_exposure_points(rows: list[Any]) -> list[ExposurePoint]:
    exposure_points: list[ExposurePoint] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        valuation_date = row.get("valuation_date")
        grouping_dimension = row.get("grouping_dimension")
        group_key = row.get("group_key")
        weight = row.get("weight")
        if not (
            isinstance(valuation_date, str)
            and isinstance(grouping_dimension, str)
            and isinstance(group_key, str)
            and weight is not None
        ):
            continue
        group_label_raw = row.get("group_label")
        group_label = str(group_label_raw) if group_label_raw is not None else None
        exposure_points.append(
            ExposurePoint(
                date=date.fromisoformat(valuation_date),
                grouping_dimension=grouping_dimension,  # type: ignore[arg-type]
                group_key=group_key,
                group_label=group_label,
                weight=float(_as_decimal(weight)),
            )
        )
    exposure_points.sort(key=lambda item: (item.date, item.grouping_dimension, item.group_key))
    return exposure_points


async def fetch_benchmark_exposure_history(
    *,
    performance_client: BenchmarkExposurePerformanceClientProtocol,
    portfolio_id: str,
    as_of_date: date,
    start_date: date,
    reporting_currency: str | None,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[ExposurePoint]:
    unsupported_groupings = sorted(
        {dimension for dimension in grouping_dimensions if dimension in {"CUSTOM", "ISSUER"}}
    )
    if unsupported_groupings:
        raise ValueError(
            "stateful ACTIVE_RISK/TRACKING_ERROR attribution cannot source benchmark "
            "exposure history for grouping_dimensions=" + ", ".join(unsupported_groupings)
        )

    page_token: str | None = None
    benchmark_exposures: list[ExposurePoint] = []
    while True:
        response = await performance_client.get_benchmark_exposure_context(
            request_payload=_build_request_payload(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                start_date=start_date,
                reporting_currency=reporting_currency,
                grouping_dimensions=grouping_dimensions,
                page_token=page_token,
            ),
            correlation_id=correlation_id,
        )
        _validate_lineage(response)

        rows = response.get("rows")
        if not isinstance(rows, list):
            raise invalid_upstream_payload(
                service="lotus-performance",
                operation="/integration/benchmarks/exposure-context",
                message="lotus-performance benchmark exposure context payload missing 'rows' list",
            )
        benchmark_exposures.extend(_rows_to_exposure_points(rows))

        page = response.get("page")
        next_page_token = page.get("next_page_token") if isinstance(page, dict) else None
        if not isinstance(next_page_token, str) or not next_page_token:
            break
        page_token = next_page_token

    if not benchmark_exposures:
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message=(
                "unable to build benchmark exposure history from lotus-performance "
                "benchmark exposure context"
            ),
        )
    return benchmark_exposures
