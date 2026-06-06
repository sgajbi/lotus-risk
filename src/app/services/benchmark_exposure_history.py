from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class BenchmarkExposureHistoryRequest:
    performance_client: BenchmarkExposurePerformanceClientProtocol
    portfolio_id: str
    as_of_date: date
    start_date: date
    reporting_currency: str | None
    grouping_dimensions: list[GroupingDimension]
    correlation_id: str | None


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
    _require_context_value(
        response,
        field_name="source_service",
        expected_value="lotus-performance",
        message="source_service=lotus-performance",
    )
    _require_context_value(
        response,
        field_name="contract_version",
        expected_value="v1",
        message="contract_version=v1",
    )

    metadata = _metadata_object(response)
    _require_context_value(
        metadata,
        field_name="source_system",
        expected_value="lotus-core",
        message="lotus-core lineage",
    )
    _require_context_value(
        metadata,
        field_name="served_by",
        expected_value="lotus-performance",
        message="served_by=lotus-performance",
    )


def _metadata_object(response: dict[str, Any]) -> dict[str, Any]:
    metadata = response.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    raise _invalid_benchmark_exposure_context("payload missing metadata object")


def _require_context_value(
    payload: dict[str, Any],
    *,
    field_name: str,
    expected_value: str,
    message: str,
) -> None:
    if payload.get(field_name) == expected_value:
        return
    raise _invalid_benchmark_exposure_context(f"missing {message}")


def _invalid_benchmark_exposure_context(message: str) -> ValueError:
    return invalid_upstream_payload(
        service="lotus-performance",
        operation="/integration/benchmarks/exposure-context",
        message=f"lotus-performance benchmark exposure context {message}",
    )


def _build_request_payload(
    *,
    request: BenchmarkExposureHistoryRequest,
    page_token: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "portfolio_id": request.portfolio_id,
        "as_of_date": request.as_of_date.isoformat(),
        "window": {
            "start_date": request.start_date.isoformat(),
            "end_date": request.as_of_date.isoformat(),
        },
        "frequency": "DAILY",
        "grouping_dimensions": request.grouping_dimensions,
        "page": {"page_size": 1000, "page_token": page_token},
    }
    if request.reporting_currency:
        payload["reporting_currency"] = request.reporting_currency
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


async def _fetch_benchmark_exposure_page(
    *,
    request: BenchmarkExposureHistoryRequest,
    page_token: str | None,
) -> tuple[list[ExposurePoint], str | None]:
    response = await request.performance_client.get_benchmark_exposure_context(
        request_payload=_build_request_payload(
            request=request,
            page_token=page_token,
        ),
        correlation_id=request.correlation_id,
    )
    _validate_lineage(response)

    rows = response.get("rows")
    if not isinstance(rows, list):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation="/integration/benchmarks/exposure-context",
            message="lotus-performance benchmark exposure context payload missing 'rows' list",
        )

    page = response.get("page")
    next_page_token = page.get("next_page_token") if isinstance(page, dict) else None
    return (
        _rows_to_exposure_points(rows),
        next_page_token if isinstance(next_page_token, str) and next_page_token else None,
    )


def _validate_supported_grouping_dimensions(
    grouping_dimensions: list[GroupingDimension],
) -> None:
    unsupported_groupings = sorted(
        {dimension for dimension in grouping_dimensions if dimension == "CUSTOM"}
    )
    if unsupported_groupings:
        raise ValueError(
            "stateful ACTIVE_RISK/TRACKING_ERROR attribution cannot source benchmark "
            "exposure history for grouping_dimensions=" + ", ".join(unsupported_groupings)
        )


async def fetch_benchmark_exposure_history(
    request: BenchmarkExposureHistoryRequest,
) -> list[ExposurePoint]:
    _validate_supported_grouping_dimensions(request.grouping_dimensions)

    page_token: str | None = None
    benchmark_exposures: list[ExposurePoint] = []
    while True:
        exposure_points, next_page_token = await _fetch_benchmark_exposure_page(
            request=request,
            page_token=page_token,
        )
        benchmark_exposures.extend(exposure_points)
        if next_page_token is None:
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
