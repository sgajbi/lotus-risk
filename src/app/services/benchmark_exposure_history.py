from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Protocol
from uuid import UUID

from app.contracts.attribution import ExposurePoint, GroupingDimension
from app.contracts.downstream_authority import DownstreamAuthority
from app.upstream_errors import (
    UpstreamServiceError,
    invalid_upstream_payload,
    missing_upstream_data,
)

BENCHMARK_EXPOSURE_CONTEXT_OPERATION = "/integration/benchmarks/exposure-context"
BENCHMARK_EXPOSURE_PAGE_SIZE = 1000
BENCHMARK_EXPOSURE_MAX_PAGES = 25
BENCHMARK_EXPOSURE_MAX_ROWS = 10000


class BenchmarkExposurePerformanceClientProtocol(Protocol):
    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class BenchmarkExposureHistoryRequest:
    performance_client: BenchmarkExposurePerformanceClientProtocol
    portfolio_id: str
    as_of_date: date
    start_date: date
    reporting_currency: str | None
    grouping_dimensions: list[GroupingDimension]
    authority: DownstreamAuthority


def _as_decimal(value: Any) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
            message=f"Invalid benchmark exposure weight from lotus-performance: {value}",
        ) from exc
    if not decimal_value.is_finite():
        raise _invalid_benchmark_exposure_context("has non-finite exposure weight")
    return decimal_value


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
    _require_context_value(
        metadata,
        field_name="contract_version",
        expected_value="v1",
        message="metadata.contract_version=v1",
    )
    _require_complete_exposure_source_quality(metadata)
    _require_calculation_identity(response, metadata)


def _require_calculation_identity(response: dict[str, Any], metadata: dict[str, Any]) -> None:
    calculation_id = response.get("calculation_id")
    if not isinstance(calculation_id, str) or metadata.get("calculation_run_id") != calculation_id:
        raise _invalid_benchmark_exposure_context("has conflicting calculation lineage")
    try:
        UUID(calculation_id)
    except ValueError as exc:
        raise _invalid_benchmark_exposure_context("has invalid calculation lineage") from exc


def _metadata_object(response: dict[str, Any]) -> dict[str, Any]:
    metadata = response.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    raise _invalid_benchmark_exposure_context("payload missing metadata object")


def _require_complete_exposure_source_quality(metadata: dict[str, Any]) -> None:
    """Reject partial economics rather than calculating from remaining exposure rows."""

    source_quality = metadata.get("exposure_source_quality")
    if not isinstance(source_quality, dict):
        raise _invalid_benchmark_exposure_context("payload missing exposure_source_quality object")
    source_status = source_quality.get("status")
    if source_status == "incomplete":
        raise missing_upstream_data(
            service="lotus-performance",
            operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
            message="lotus-performance benchmark exposure context reports incomplete economic source evidence",
        )
    if source_status != "complete":
        raise _invalid_benchmark_exposure_context("has unknown exposure_source_quality status")

    if not _complete_source_quality_has_no_omissions(source_quality):
        raise _invalid_benchmark_exposure_context(
            "has contradictory complete exposure_source_quality omissions"
        )


def _complete_source_quality_has_no_omissions(source_quality: dict[str, Any]) -> bool:
    counts = (
        source_quality.get("omitted_component_count"),
        source_quality.get("omitted_point_count"),
    )
    return (
        all(
            isinstance(value, int) and not isinstance(value, bool) and value == 0
            for value in counts
        )
        and source_quality.get("reason_codes") == []
        and source_quality.get("omissions") == []
        and source_quality.get("omissions_truncated") is False
    )


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
        operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
        message=f"lotus-performance benchmark exposure context {message}",
    )


def _invalid_benchmark_exposure_pagination(
    *,
    reason: str,
    page_count: int,
    row_count: int,
) -> ValueError:
    return invalid_upstream_payload(
        service="lotus-performance",
        operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
        message="lotus-performance benchmark exposure context unsafe pagination",
        details={
            "reason": reason,
            "page_count": page_count,
            "row_count": row_count,
            "max_pages": BENCHMARK_EXPOSURE_MAX_PAGES,
            "max_rows": BENCHMARK_EXPOSURE_MAX_ROWS,
        },
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
        "page": {"page_size": BENCHMARK_EXPOSURE_PAGE_SIZE, "page_token": page_token},
    }
    if request.reporting_currency:
        payload["reporting_currency"] = request.reporting_currency
    return payload


def _rows_to_exposure_points(rows: list[Any]) -> list[ExposurePoint]:
    exposure_points = [_row_to_exposure_point(row, index) for index, row in enumerate(rows)]
    exposure_points.sort(key=lambda item: (item.date, item.grouping_dimension, item.group_key))
    return exposure_points


def _row_to_exposure_point(row: Any, index: int) -> ExposurePoint:
    if not isinstance(row, dict):
        raise _invalid_benchmark_exposure_context(f"has invalid exposure row at index {index}")
    valuation_date = row.get("valuation_date")
    grouping_dimension = row.get("grouping_dimension")
    group_key = row.get("group_key")
    weight = row.get("weight")
    if not (
        isinstance(valuation_date, str)
        and isinstance(grouping_dimension, str)
        and isinstance(group_key, str)
        and group_key
        and weight is not None
    ):
        raise _invalid_benchmark_exposure_context(f"has incomplete exposure row at index {index}")
    group_label_raw = row.get("group_label")
    if group_label_raw is not None and not isinstance(group_label_raw, str):
        raise _invalid_benchmark_exposure_context(f"has invalid exposure label at index {index}")
    observation_date, finite_weight = _parse_exposure_date_weight(valuation_date, weight, index)
    try:
        return ExposurePoint(
            date=observation_date,
            grouping_dimension=grouping_dimension,  # type: ignore[arg-type]
            group_key=group_key,
            group_label=group_label_raw,
            weight=finite_weight,
        )
    except ValueError as exc:
        raise _invalid_benchmark_exposure_context(
            f"has invalid exposure row at index {index}"
        ) from exc


def _parse_exposure_date_weight(valuation_date: str, weight: Any, index: int) -> tuple[date, float]:
    try:
        observation_date = date.fromisoformat(valuation_date)
        if observation_date.isoformat() != valuation_date:
            raise ValueError("non-canonical date")
        finite_weight = float(_as_decimal(weight))
        if not isfinite(finite_weight):
            raise ValueError("non-finite float weight")
        return observation_date, finite_weight
    except UpstreamServiceError:
        raise
    except ValueError as exc:
        raise _invalid_benchmark_exposure_context(
            f"has invalid exposure row at index {index}"
        ) from exc


async def _fetch_benchmark_exposure_page(
    *,
    request: BenchmarkExposureHistoryRequest,
    page_token: str | None,
) -> tuple[list[ExposurePoint], str | None, tuple[str, str]]:
    response = await request.performance_client.get_benchmark_exposure_context(
        request_payload=_build_request_payload(
            request=request,
            page_token=page_token,
        ),
        authority=request.authority,
    )
    _validate_lineage(response)
    _validate_response_scope(response=response, request=request)

    rows = response.get("rows")
    if not isinstance(rows, list):
        raise invalid_upstream_payload(
            service="lotus-performance",
            operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
            message="lotus-performance benchmark exposure context payload missing 'rows' list",
        )

    next_page_token = _next_benchmark_page_token(response.get("page"))
    benchmark_identity = _benchmark_identity(response)
    exposure_points = _rows_to_exposure_points(rows)
    for point in exposure_points:
        if (
            point.date < request.start_date
            or point.date > request.as_of_date
            or point.grouping_dimension not in request.grouping_dimensions
        ):
            raise _invalid_benchmark_exposure_context("has exposure row outside requested scope")
    return exposure_points, next_page_token, benchmark_identity


def _next_benchmark_page_token(page: Any) -> str | None:
    if not isinstance(page, dict) or "next_page_token" not in page:
        raise _invalid_benchmark_exposure_context("has missing pagination metadata")
    token = page["next_page_token"]
    if token is None or (isinstance(token, str) and token):
        return token
    raise _invalid_benchmark_exposure_context("has invalid next_page_token")


def _benchmark_identity(response: dict[str, Any]) -> tuple[str, str]:
    benchmark_id = response.get("benchmark_id")
    benchmark_version = response.get("benchmark_version")
    if not (
        isinstance(benchmark_id, str)
        and benchmark_id.strip()
        and isinstance(benchmark_version, str)
        and benchmark_version.strip()
    ):
        raise _invalid_benchmark_exposure_context("has missing benchmark identity")
    return benchmark_id, benchmark_version


def _validate_response_scope(
    *, response: dict[str, Any], request: BenchmarkExposureHistoryRequest
) -> None:
    expected: dict[str, Any] = {
        "portfolio_id": request.portfolio_id,
        "as_of_date": request.as_of_date.isoformat(),
        "window": {
            "start_date": request.start_date.isoformat(),
            "end_date": request.as_of_date.isoformat(),
        },
        "frequency": "DAILY",
        "reporting_currency": request.reporting_currency,
    }
    for field_name, value in expected.items():
        if response.get(field_name) != value:
            raise _invalid_benchmark_exposure_context(
                f"has {field_name} inconsistent with the admitted request"
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
    rows, _ = await fetch_benchmark_exposure_history_with_identity(request)
    return rows


async def fetch_benchmark_exposure_history_with_identity(
    request: BenchmarkExposureHistoryRequest,
) -> tuple[list[ExposurePoint], tuple[str, str]]:
    _validate_supported_grouping_dimensions(request.grouping_dimensions)

    page_token: str | None = None
    benchmark_exposures: list[ExposurePoint] = []
    seen_page_tokens: set[str] = set()
    seen_row_keys: set[tuple[date, str, str]] = set()
    expected_benchmark_identity: tuple[str, str] | None = None
    page_count = 0
    while True:
        exposure_points, next_page_token, benchmark_identity = await _fetch_benchmark_exposure_page(
            request=request,
            page_token=page_token,
        )
        page_count += 1
        expected_benchmark_identity = _validate_page_identity_and_rows(
            points=exposure_points,
            identity=benchmark_identity,
            expected_identity=expected_benchmark_identity,
            seen_row_keys=seen_row_keys,
        )
        benchmark_exposures.extend(exposure_points)
        if len(benchmark_exposures) > BENCHMARK_EXPOSURE_MAX_ROWS:
            raise _invalid_benchmark_exposure_pagination(
                reason="max_rows_exceeded",
                page_count=page_count,
                row_count=len(benchmark_exposures),
            )
        if next_page_token is None:
            break
        if next_page_token in seen_page_tokens or next_page_token == page_token:
            raise _invalid_benchmark_exposure_pagination(
                reason="repeated_page_token",
                page_count=page_count,
                row_count=len(benchmark_exposures),
            )
        if page_count >= BENCHMARK_EXPOSURE_MAX_PAGES:
            raise _invalid_benchmark_exposure_pagination(
                reason="max_pages_exceeded",
                page_count=page_count,
                row_count=len(benchmark_exposures),
            )
        seen_page_tokens.add(next_page_token)
        page_token = next_page_token

    if not benchmark_exposures:
        raise missing_upstream_data(
            service="lotus-performance",
            operation=BENCHMARK_EXPOSURE_CONTEXT_OPERATION,
            message=(
                "unable to build benchmark exposure history from lotus-performance "
                "benchmark exposure context"
            ),
        )
    if expected_benchmark_identity is None:
        raise _invalid_benchmark_exposure_context("missing benchmark identity")
    return benchmark_exposures, expected_benchmark_identity


def _validate_page_identity_and_rows(
    *,
    points: list[ExposurePoint],
    identity: tuple[str, str],
    expected_identity: tuple[str, str] | None,
    seen_row_keys: set[tuple[date, str, str]],
) -> tuple[str, str]:
    if expected_identity is not None and identity != expected_identity:
        raise _invalid_benchmark_exposure_context("has changed benchmark identity across pages")
    for point in points:
        row_key = (point.date, point.grouping_dimension, point.group_key)
        if row_key in seen_row_keys:
            raise _invalid_benchmark_exposure_context("has duplicate exposure row across pages")
        seen_row_keys.add(row_key)
    return identity
