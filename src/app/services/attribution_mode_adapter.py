from __future__ import annotations

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
from app.contracts.risk import RiskRequestScope
from app.services.attribution_engine import calculate_historical_attribution
from app.services.stateful_returns_request import build_stateful_returns_series_request
from app.services.stateful_returns_series_parser import extract_required_portfolio_returns


class LotusPerformanceClientProtocol(Protocol):
    async def get_returns_series(
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


def _build_stateful_returns_request(stateful: HistoricalAttributionStatefulInput) -> dict[str, Any]:
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=False,
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
    dimensions: list[str] = []
    if "SECTOR" in grouping_dimensions:
        dimensions.append("sector")
    if "ASSET_CLASS" in grouping_dimensions:
        dimensions.append("asset_class")

    page_token: str | None = None
    rows: list[dict[str, Any]] = []
    while True:
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

        response = await core_client.get_position_analytics_timeseries(
            portfolio_id=portfolio_id,
            request_payload=payload,
            correlation_id=correlation_id,
        )
        batch = response.get("rows")
        if not isinstance(batch, list):
            raise ValueError("lotus-core position-timeseries payload missing 'rows' list")
        for row in batch:
            if isinstance(row, dict):
                rows.append(row)

        page = response.get("page")
        next_page_token = page.get("next_page_token") if isinstance(page, dict) else None
        if not isinstance(next_page_token, str) or not next_page_token:
            break
        page_token = next_page_token
    return rows


async def _build_issuer_map(
    *,
    core_client: LotusCoreClientProtocol,
    rows: list[dict[str, Any]],
    correlation_id: str | None,
) -> dict[str, tuple[str, str | None]]:
    security_ids = sorted(
        {
            str(row.get("security_id"))
            for row in rows
            if isinstance(row, dict) and row.get("security_id")
        }
    )
    if not security_ids:
        return {}
    response = await core_client.get_instrument_enrichment(
        security_ids=security_ids,
        correlation_id=correlation_id,
    )
    records = response.get("records")
    if not isinstance(records, list):
        raise ValueError("lotus-core enrichment payload missing 'records' list")
    issuer_map: dict[str, tuple[str, str | None]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        security_id_raw = record.get("security_id")
        if not security_id_raw:
            continue
        security_id = str(security_id_raw)
        issuer_id_raw = record.get("issuer_id")
        issuer_name_raw = record.get("issuer_name")
        issuer_id = str(issuer_id_raw) if issuer_id_raw else f"ISSUER_{security_id}"
        issuer_name = str(issuer_name_raw) if issuer_name_raw else None
        issuer_map[security_id] = (issuer_id, issuer_name)
    return issuer_map


async def calculate_historical_attribution_stateful(
    stateful: HistoricalAttributionStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> HistoricalAttributionResponse:
    options = stateful.attribution_options
    requested_groupings = options.grouping_dimensions
    if "CUSTOM" in requested_groupings:
        raise ValueError(
            "stateful historical-attribution does not support grouping_dimension=CUSTOM"
        )

    requires_active = (
        "ACTIVE_RISK" in options.attribution_types or "TRACKING_ERROR" in options.metrics
    )
    if requires_active:
        raise ValueError(
            "stateful ACTIVE_RISK/TRACKING_ERROR attribution is blocked until benchmark exposure history contract is available"
        )

    returns_response = await performance_client.get_returns_series(
        request_payload=_build_stateful_returns_request(stateful),
        correlation_id=correlation_id,
    )
    _, portfolio_returns = extract_required_portfolio_returns(returns_response)
    start_date = min(point.date for point in portfolio_returns)

    rows = await _fetch_position_timeseries_rows(
        core_client=core_client,
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        start_date=start_date,
        reporting_currency=stateful.reporting_currency,
        grouping_dimensions=requested_groupings,
        correlation_id=correlation_id,
    )
    if not rows:
        raise ValueError("lotus-core position-timeseries returned no rows")

    issuer_map = (
        await _build_issuer_map(
            core_client=core_client,
            rows=rows,
            correlation_id=correlation_id,
        )
        if "ISSUER" in requested_groupings
        else {}
    )
    exposure_history = _build_exposure_points(
        rows=rows,
        grouping_dimensions=requested_groupings,
        issuer_map=issuer_map,
    )
    if not exposure_history:
        raise ValueError("unable to build exposure history from lotus-core position-timeseries")

    stateless_input = HistoricalAttributionStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=portfolio_returns,
        benchmark_returns=[],
        exposure_history=exposure_history,
        benchmark_exposure_history=[],
        attribution_options=options,
    )
    return calculate_historical_attribution(
        stateless_input,
        input_mode=AttributionInputMode.STATEFUL,
    )

