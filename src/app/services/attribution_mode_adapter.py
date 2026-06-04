from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.contracts.attribution import (
    AttributionInputMode,
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionResponse,
    HistoricalAttributionStatefulInput,
    HistoricalAttributionStatelessInput,
)
from app.contracts.risk import ReturnPoint, RiskRequestScope
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint
from app.services.attribution_engine import calculate_historical_attribution
from app.services.benchmark_exposure_history import fetch_benchmark_exposure_history
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import (
    extract_required_portfolio_returns,
    to_return_points,
)
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_benchmark_exposure_context(
        self,
        *,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


class LotusCoreClientProtocol(Protocol):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class _StatefulReturnsContext:
    returns_request: dict[str, Any]
    portfolio_returns: list[ReturnPoint]
    benchmark_returns: list[ReturnPoint]
    start_date: date


def _requires_active_attribution(stateful: HistoricalAttributionStatefulInput) -> bool:
    options = stateful.attribution_options
    return "ACTIVE_RISK" in options.attribution_types or "TRACKING_ERROR" in options.metrics


def _validate_benchmark_exposure_alignment(
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


def _build_stateful_returns_request(stateful: HistoricalAttributionStatefulInput) -> dict[str, Any]:
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=_requires_active_attribution(stateful),
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )


def _group_key_and_label(
    *,
    row: dict[str, Any],
    grouping_dimension: GroupingDimension,
    issuer_map: dict[str, tuple[str, str | None]],
) -> tuple[str, str | None]:
    security_id_raw = row.get("security_id")
    security_id = str(security_id_raw) if security_id_raw else "UNKNOWN_SECURITY"
    dimensions_raw = row.get("dimensions")
    dimensions = dimensions_raw if isinstance(dimensions_raw, dict) else {}

    if grouping_dimension == "POSITION":
        return security_id, security_id
    if grouping_dimension == "SECTOR":
        sector = dimensions.get("sector")
        label = str(sector) if sector else "UNKNOWN"
        return f"SECTOR_{label}", label
    if grouping_dimension == "ASSET_CLASS":
        asset_class = dimensions.get("asset_class")
        label = str(asset_class) if asset_class else "UNKNOWN"
        return f"ASSET_CLASS_{label}", label
    if grouping_dimension == "ISSUER":
        issuer_id, issuer_name = issuer_map.get(security_id, (f"ISSUER_{security_id}", None))
        return issuer_id, issuer_name
    raise ValueError(f"Unsupported stateful grouping_dimension={grouping_dimension}")


def _as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Invalid market value from lotus-core position-timeseries: {value}"
        ) from exc


def _build_exposure_points(
    *,
    rows: list[dict[str, Any]],
    grouping_dimensions: list[GroupingDimension],
    issuer_map: dict[str, tuple[str, str | None]],
) -> list[ExposurePoint]:
    grouped_values: dict[tuple[date, GroupingDimension, str], Decimal] = {}
    totals_by_date: dict[date, Decimal] = {}
    labels: dict[tuple[GroupingDimension, str], str | None] = {}

    for row in rows:
        valuation_date = row.get("valuation_date")
        if not isinstance(valuation_date, str):
            continue
        obs_date = date.fromisoformat(valuation_date)
        ending_reporting = row.get("ending_market_value_reporting_currency")
        ending_portfolio = row.get("ending_market_value_portfolio_currency")
        market_value = _as_decimal(
            ending_reporting if ending_reporting is not None else ending_portfolio
        )
        totals_by_date[obs_date] = totals_by_date.get(obs_date, Decimal("0")) + market_value

        for grouping_dimension in grouping_dimensions:
            group_key, group_label = _group_key_and_label(
                row=row,
                grouping_dimension=grouping_dimension,
                issuer_map=issuer_map,
            )
            labels[(grouping_dimension, group_key)] = group_label
            key = (obs_date, grouping_dimension, group_key)
            grouped_values[key] = grouped_values.get(key, Decimal("0")) + market_value

    points: list[ExposurePoint] = []
    for (obs_date, grouping_dimension, group_key), value in grouped_values.items():
        total = totals_by_date.get(obs_date, Decimal("0"))
        if total == 0:
            continue
        points.append(
            ExposurePoint(
                date=obs_date,
                grouping_dimension=grouping_dimension,
                group_key=group_key,
                group_label=labels.get((grouping_dimension, group_key)),
                weight=float(value / total),
            )
        )
    points.sort(key=lambda item: (item.date, item.grouping_dimension, item.group_key))
    return points


def _position_timeseries_dimensions(grouping_dimensions: list[GroupingDimension]) -> list[str]:
    dimensions: list[str] = []
    if "SECTOR" in grouping_dimensions:
        dimensions.append("sector")
    if "ASSET_CLASS" in grouping_dimensions:
        dimensions.append("asset_class")
    return dimensions


def _position_timeseries_payload(
    *,
    as_of_date: date,
    start_date: date,
    reporting_currency: str | None,
    dimensions: list[str],
    page_token: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "as_of_date": as_of_date.isoformat(),
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": as_of_date.isoformat(),
        },
        "frequency": "daily",
        "dimensions": dimensions,
        "consumer_system": "lotus-risk",
        "page": {"page_size": 5000, "page_token": page_token},
    }
    if reporting_currency:
        payload["reporting_currency"] = reporting_currency
    return payload


def _extract_position_rows_batch(
    *,
    response: dict[str, Any],
    portfolio_id: str,
) -> list[dict[str, Any]]:
    batch = response.get("rows")
    if not isinstance(batch, list):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation=f"/integration/portfolios/{portfolio_id}/analytics/position-timeseries",
            message="lotus-core position-timeseries payload missing 'rows' list",
        )
    return [row for row in batch if isinstance(row, dict)]


def _next_position_page_token(response: dict[str, Any]) -> str | None:
    page = response.get("page")
    next_page_token = page.get("next_page_token") if isinstance(page, dict) else None
    return next_page_token if isinstance(next_page_token, str) and next_page_token else None


async def _fetch_position_timeseries_rows(
    *,
    core_client: LotusCoreClientProtocol,
    portfolio_id: str,
    as_of_date: date,
    start_date: date,
    reporting_currency: str | None,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[dict[str, Any]]:
    dimensions = _position_timeseries_dimensions(grouping_dimensions)
    page_token: str | None = None
    rows: list[dict[str, Any]] = []
    while True:
        response = await core_client.get_position_analytics_timeseries(
            portfolio_id=portfolio_id,
            request_payload=_position_timeseries_payload(
                as_of_date=as_of_date,
                start_date=start_date,
                reporting_currency=reporting_currency,
                dimensions=dimensions,
                page_token=page_token,
            ),
            correlation_id=correlation_id,
        )
        rows.extend(_extract_position_rows_batch(response=response, portfolio_id=portfolio_id))
        page_token = _next_position_page_token(response)
        if page_token is None:
            break
    return rows


def _security_ids_from_position_rows(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("security_id"))
            for row in rows
            if isinstance(row, dict) and row.get("security_id")
        }
    )


def _issuer_identity_from_record(
    record: dict[str, Any],
) -> tuple[str, tuple[str, str | None]] | None:
    security_id_raw = record.get("security_id")
    if not security_id_raw:
        return None
    security_id = str(security_id_raw)
    issuer_id_raw = record.get("issuer_id")
    issuer_name_raw = record.get("issuer_name")
    issuer_id = str(issuer_id_raw) if issuer_id_raw else f"ISSUER_{security_id}"
    issuer_name = str(issuer_name_raw) if issuer_name_raw else None
    return security_id, (issuer_id, issuer_name)


async def _build_issuer_map(
    *,
    core_client: LotusCoreClientProtocol,
    rows: list[dict[str, Any]],
    correlation_id: str | None,
) -> dict[str, tuple[str, str | None]]:
    security_ids = _security_ids_from_position_rows(rows)
    if not security_ids:
        return {}
    response = await core_client.get_instrument_enrichment(
        security_ids=security_ids,
        correlation_id=correlation_id,
    )
    records = response.get("records")
    if not isinstance(records, list):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation="/integration/instruments/enrichment-bulk",
            message="lotus-core enrichment payload missing 'records' list",
        )
    issuer_map: dict[str, tuple[str, str | None]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        issuer_identity = _issuer_identity_from_record(record)
        if issuer_identity is not None:
            security_id, issuer = issuer_identity
            issuer_map[security_id] = issuer
    return issuer_map


def _validate_stateful_groupings(grouping_dimensions: list[GroupingDimension]) -> None:
    if "CUSTOM" in grouping_dimensions:
        raise ValueError(
            "stateful historical-attribution does not support grouping_dimension=CUSTOM"
        )


async def _fetch_stateful_returns_context(
    *,
    stateful: HistoricalAttributionStatefulInput,
    performance_client: LotusPerformanceClientProtocol,
    correlation_id: str | None,
) -> _StatefulReturnsContext:
    returns_request = _build_stateful_returns_request(stateful)
    returns_response = await performance_client.get_returns_series(
        request_payload=returns_request,
        correlation_id=correlation_id,
    )
    series, portfolio_returns = extract_required_portfolio_returns(returns_response)
    benchmark_returns = to_return_points(series.get("benchmark_returns"))
    if _requires_active_attribution(stateful) and not benchmark_returns:
        raise missing_upstream_data(
            service="lotus-performance",
            operation="/integration/returns/series",
            message=(
                "lotus-performance returns-series returned no benchmark returns for "
                "requested stateful active-risk attribution"
            ),
        )
    return _StatefulReturnsContext(
        returns_request=returns_request,
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        start_date=min(point.date for point in portfolio_returns),
    )


async def _fetch_stateful_exposure_history(
    *,
    stateful: HistoricalAttributionStatefulInput,
    core_client: LotusCoreClientProtocol,
    start_date: date,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[ExposurePoint]:
    rows = await _fetch_position_timeseries_rows(
        core_client=core_client,
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        start_date=start_date,
        reporting_currency=stateful.reporting_currency,
        grouping_dimensions=grouping_dimensions,
        correlation_id=correlation_id,
    )
    if not rows:
        raise missing_upstream_data(
            service="lotus-core",
            operation=f"/integration/portfolios/{stateful.portfolio_id}/analytics/position-timeseries",
            message="lotus-core position-timeseries returned no rows",
        )

    issuer_map = (
        await _build_issuer_map(
            core_client=core_client,
            rows=rows,
            correlation_id=correlation_id,
        )
        if "ISSUER" in grouping_dimensions
        else {}
    )
    exposure_history = _build_exposure_points(
        rows=rows,
        grouping_dimensions=grouping_dimensions,
        issuer_map=issuer_map,
    )
    if not exposure_history:
        raise missing_upstream_data(
            service="lotus-core",
            operation=f"/integration/portfolios/{stateful.portfolio_id}/analytics/position-timeseries",
            message="unable to build exposure history from lotus-core position-timeseries",
        )
    return exposure_history


async def _fetch_active_benchmark_exposure_history(
    *,
    stateful: HistoricalAttributionStatefulInput,
    performance_client: LotusPerformanceClientProtocol,
    benchmark_returns: list[ReturnPoint],
    start_date: date,
    grouping_dimensions: list[GroupingDimension],
    correlation_id: str | None,
) -> list[ExposurePoint]:
    benchmark_exposure_history = await fetch_benchmark_exposure_history(
        performance_client=performance_client,
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        start_date=start_date,
        reporting_currency=stateful.reporting_currency,
        grouping_dimensions=grouping_dimensions,
        correlation_id=correlation_id,
    )
    _validate_benchmark_exposure_alignment(
        benchmark_returns=benchmark_returns,
        benchmark_exposure_history=benchmark_exposure_history,
    )
    return benchmark_exposure_history


def _build_stateful_stateless_input(
    *,
    stateful: HistoricalAttributionStatefulInput,
    returns_context: _StatefulReturnsContext,
    exposure_history: list[ExposurePoint],
    benchmark_exposure_history: list[ExposurePoint],
) -> HistoricalAttributionStatelessInput:
    return HistoricalAttributionStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=returns_context.portfolio_returns,
        benchmark_returns=returns_context.benchmark_returns,
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
        attribution_options=stateful.attribution_options,
    )


def _attach_stateful_lineage(
    *,
    response: HistoricalAttributionResponse,
    returns_request: dict[str, Any],
) -> HistoricalAttributionResponse:
    response.metadata.source_services = ordered_source_services(
        "lotus-performance",
        "lotus-core",
    )
    response.metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=returns_request,
    )
    return response


async def calculate_historical_attribution_stateful(
    stateful: HistoricalAttributionStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> HistoricalAttributionResponse:
    options = stateful.attribution_options
    requested_groupings = options.grouping_dimensions
    _validate_stateful_groupings(requested_groupings)

    requires_active = _requires_active_attribution(stateful)
    returns_context = await _fetch_stateful_returns_context(
        stateful=stateful,
        performance_client=performance_client,
        correlation_id=correlation_id,
    )
    exposure_history = await _fetch_stateful_exposure_history(
        stateful=stateful,
        core_client=core_client,
        start_date=returns_context.start_date,
        grouping_dimensions=requested_groupings,
        correlation_id=correlation_id,
    )

    benchmark_exposure_history = (
        await _fetch_active_benchmark_exposure_history(
            stateful=stateful,
            performance_client=performance_client,
            benchmark_returns=returns_context.benchmark_returns,
            start_date=returns_context.start_date,
            grouping_dimensions=requested_groupings,
            correlation_id=correlation_id,
        )
        if requires_active
        else []
    )
    stateless_input = _build_stateful_stateless_input(
        stateful=stateful,
        returns_context=returns_context,
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
    )
    response = calculate_historical_attribution(
        stateless_input,
        input_mode=AttributionInputMode.STATEFUL,
    )
    return _attach_stateful_lineage(
        response=response,
        returns_request=returns_context.returns_request,
    )
