from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from app.contracts.rolling import RollingStatefulInput
from app.services.core_risk_free_series import build_risk_free_series_request
from app.services.rolling_stateful_dependency_selection import requires_benchmark
from app.services.rolling_stateful_models import (
    LotusCoreClientProtocol,
    LotusPerformanceClientProtocol,
    StatefulSourceResponses,
)
from app.services.stateful_returns_request import build_stateful_returns_series_request


def build_stateful_source_request(stateful: RollingStatefulInput) -> dict[str, Any]:
    return build_stateful_returns_series_request(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        periods=stateful.periods,
        frequency="DAILY",
        metric_basis=stateful.net_or_gross,
        reporting_currency=stateful.reporting_currency,
        include_benchmark=requires_benchmark(stateful),
        include_risk_free=False,
        missing_data_policy="ALLOW_PARTIAL",
    )


def explicit_window_bounds(source_payload: dict[str, Any]) -> tuple[date, date] | None:
    window = source_payload.get("window")
    if not isinstance(window, dict):
        return None
    if window.get("mode") != "EXPLICIT":
        return None

    raw_start = window.get("from_date")
    raw_end = window.get("to_date")
    if not isinstance(raw_start, str) or not isinstance(raw_end, str):
        return None
    return date.fromisoformat(raw_start), date.fromisoformat(raw_end)


async def fetch_stateful_source_responses(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
    include_risk_free: bool,
    reporting_currency: str | None,
) -> StatefulSourceResponses:
    source_payload = build_stateful_source_request(stateful)
    explicit_window = explicit_window_bounds(source_payload)
    risk_free_request, checked_core_client = _explicit_risk_free_request(
        stateful=stateful,
        core_client=core_client,
        include_risk_free=include_risk_free,
        explicit_window=explicit_window,
        reporting_currency=reporting_currency,
    )
    source_response, risk_free_response = await _fetch_returns_and_risk_free_responses(
        source_payload=source_payload,
        risk_free_request=risk_free_request,
        performance_client=performance_client,
        core_client=checked_core_client,
        correlation_id=correlation_id,
    )
    return StatefulSourceResponses(
        source_payload=source_payload,
        source_response=source_response,
        risk_free_request=risk_free_request,
        risk_free_response=risk_free_response,
    )


def _explicit_risk_free_request(
    *,
    stateful: RollingStatefulInput,
    core_client: LotusCoreClientProtocol | None,
    include_risk_free: bool,
    explicit_window: tuple[date, date] | None,
    reporting_currency: str | None,
) -> tuple[dict[str, Any] | None, LotusCoreClientProtocol | None]:
    if not include_risk_free:
        return None, None
    if core_client is None:
        raise ValueError(
            "lotus-core client is required for rolling Sharpe stateful risk-free sourcing"
        )
    if explicit_window is None:
        return None, core_client
    if reporting_currency is None:
        raise ValueError("reporting currency is required for rolling risk-free sourcing")
    return (
        build_risk_free_series_request(
            currency=reporting_currency,
            as_of_date=stateful.as_of_date,
            start_date=explicit_window[0],
            end_date=explicit_window[1],
        ),
        core_client,
    )


async def _fetch_returns_and_risk_free_responses(
    *,
    source_payload: dict[str, Any],
    risk_free_request: dict[str, Any] | None,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if risk_free_request is not None and core_client is not None:
        source_response, risk_free_response = await asyncio.gather(
            performance_client.get_returns_series(
                request_payload=source_payload,
                correlation_id=correlation_id,
            ),
            core_client.get_risk_free_series(
                request_payload=risk_free_request,
                correlation_id=correlation_id,
            ),
        )
        return source_response, risk_free_response
    source_response = await performance_client.get_returns_series(
        request_payload=source_payload,
        correlation_id=correlation_id,
    )
    return source_response, None


__all__ = [
    "build_stateful_source_request",
    "explicit_window_bounds",
    "fetch_stateful_source_responses",
]
