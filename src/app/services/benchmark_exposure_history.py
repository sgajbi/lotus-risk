from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.attribution import ExposurePoint, GroupingDimension


class BenchmarkExposureCoreClientProtocol(Protocol):
    async def resolve_benchmark_assignment(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_benchmark_market_series(
        self,
        *,
        benchmark_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def list_index_catalog(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


def _as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid benchmark exposure weight from lotus-core: {value}") from exc


async def _resolve_benchmark_id(
    *,
    core_client: BenchmarkExposureCoreClientProtocol,
    portfolio_id: str,
    as_of_date: date,
    correlation_id: str | None,
) -> str:
    response = await core_client.resolve_benchmark_assignment(
        portfolio_id=portfolio_id,
        request_payload={"as_of_date": as_of_date.isoformat()},
        correlation_id=correlation_id,
    )
    benchmark_id = response.get("benchmark_id")
    if not isinstance(benchmark_id, str) or not benchmark_id:
        raise ValueError("lotus-core benchmark-assignment payload missing benchmark_id")
    return benchmark_id


async def _build_index_classification_map(
    *,
    core_client: BenchmarkExposureCoreClientProtocol,
    as_of_date: date,
    correlation_id: str | None,
) -> dict[str, dict[str, str]]:
    response = await core_client.list_index_catalog(
        request_payload={"as_of_date": as_of_date.isoformat()},
        correlation_id=correlation_id,
    )
    records = response.get("records")
    if not isinstance(records, list):
        raise ValueError("lotus-core index catalog payload missing 'records' list")

    classifications: dict[str, dict[str, str]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        index_id_raw = record.get("index_id")
        labels_raw = record.get("classification_labels")
        if not index_id_raw or not isinstance(labels_raw, dict):
            continue
        classifications[str(index_id_raw)] = {
            str(key): str(value) for key, value in labels_raw.items() if value is not None
        }
    return classifications


def _benchmark_group_key_and_label(
    *,
    index_id: str,
    grouping_dimension: GroupingDimension,
    index_classifications: dict[str, dict[str, str]],
) -> tuple[str, str | None]:
    if grouping_dimension == "POSITION":
        return index_id, index_id
    if grouping_dimension == "SECTOR":
        label = index_classifications.get(index_id, {}).get("sector") or "UNKNOWN"
        return f"SECTOR_{label}", label
    if grouping_dimension == "ASSET_CLASS":
        label = index_classifications.get(index_id, {}).get("asset_class") or "UNKNOWN"
        return f"ASSET_CLASS_{label}", label
    raise ValueError(
        "stateful ACTIVE_RISK/TRACKING_ERROR attribution only supports benchmark "
        f"grouping_dimension=POSITION, SECTOR, or ASSET_CLASS; received {grouping_dimension}"
    )


def _build_benchmark_exposure_points(
    *,
    component_series: list[dict[str, Any]],
    grouping_dimensions: list[GroupingDimension],
    index_classifications: dict[str, dict[str, str]],
) -> list[ExposurePoint]:
    grouped_values: dict[tuple[date, GroupingDimension, str], Decimal] = {}
    labels: dict[tuple[GroupingDimension, str], str | None] = {}

    for component in component_series:
        if not isinstance(component, dict):
            continue
        index_id_raw = component.get("index_id")
        if not index_id_raw:
            continue
        index_id = str(index_id_raw)
        points = component.get("points")
        if not isinstance(points, list):
            continue

        for point in points:
            if not isinstance(point, dict):
                continue
            raw_date = point.get("series_date")
            if not isinstance(raw_date, str):
                continue
            raw_weight = point.get("component_weight")
            if raw_weight is None:
                continue
            obs_date = date.fromisoformat(raw_date)
            weight = _as_decimal(raw_weight)
            for grouping_dimension in grouping_dimensions:
                group_key, group_label = _benchmark_group_key_and_label(
                    index_id=index_id,
                    grouping_dimension=grouping_dimension,
                    index_classifications=index_classifications,
                )
                labels[(grouping_dimension, group_key)] = group_label
                key = (obs_date, grouping_dimension, group_key)
                grouped_values[key] = grouped_values.get(key, Decimal("0")) + weight

    exposure_points = [
        ExposurePoint(
            date=obs_date,
            grouping_dimension=grouping_dimension,
            group_key=group_key,
            group_label=labels.get((grouping_dimension, group_key)),
            weight=float(weight),
        )
        for (obs_date, grouping_dimension, group_key), weight in grouped_values.items()
    ]
    exposure_points.sort(key=lambda item: (item.date, item.grouping_dimension, item.group_key))
    return exposure_points


async def fetch_benchmark_exposure_history(
    *,
    core_client: BenchmarkExposureCoreClientProtocol,
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

    benchmark_id = await _resolve_benchmark_id(
        core_client=core_client,
        portfolio_id=portfolio_id,
        as_of_date=as_of_date,
        correlation_id=correlation_id,
    )

    index_classifications: dict[str, dict[str, str]] = {}
    if "SECTOR" in grouping_dimensions or "ASSET_CLASS" in grouping_dimensions:
        index_classifications = await _build_index_classification_map(
            core_client=core_client,
            as_of_date=as_of_date,
            correlation_id=correlation_id,
        )

    page_token: str | None = None
    component_series: list[dict[str, Any]] = []
    while True:
        payload: dict[str, Any] = {
            "as_of_date": as_of_date.isoformat(),
            "window": {
                "start_date": start_date.isoformat(),
                "end_date": as_of_date.isoformat(),
            },
            "frequency": "daily",
            "series_fields": ["component_weight"],
            "page": {"page_size": 1000, "page_token": page_token},
        }
        if reporting_currency:
            payload["target_currency"] = reporting_currency

        response = await core_client.get_benchmark_market_series(
            benchmark_id=benchmark_id,
            request_payload=payload,
            correlation_id=correlation_id,
        )
        batch = response.get("component_series")
        if not isinstance(batch, list):
            raise ValueError(
                "lotus-core benchmark market-series payload missing 'component_series' list"
            )
        component_series.extend(component for component in batch if isinstance(component, dict))

        page = response.get("page")
        next_page_token = page.get("next_page_token") if isinstance(page, dict) else None
        if not isinstance(next_page_token, str) or not next_page_token:
            break
        page_token = next_page_token

    benchmark_exposures = _build_benchmark_exposure_points(
        component_series=component_series,
        grouping_dimensions=grouping_dimensions,
        index_classifications=index_classifications,
    )
    if not benchmark_exposures:
        raise ValueError(
            "unable to build benchmark exposure history from lotus-core benchmark market-series"
        )
    return benchmark_exposures
