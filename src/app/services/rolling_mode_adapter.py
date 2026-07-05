from __future__ import annotations

from datetime import date
from typing import Any

from app.contracts.risk import ReturnPoint, RiskRequestScope
from app.contracts.rolling import (
    RollingInputMode,
    RollingResponse,
    RollingStatefulInput,
    RollingStatelessInput,
)
from app.contracts.rolling_common_inputs import (
    ROLLING_MAX_STATELESS_OBSERVATIONS,
    validate_rolling_time_series_workload,
)
from app.services.audit_lineage import (
    ordered_source_services,
    upstream_request_fingerprint,
)
from app.services.rolling_engine import calculate_rolling_metrics
from app.services.rolling_stateful_inputs import (
    LotusCoreClientProtocol,
    LotusPerformanceClientProtocol,
    ResolvedStatefulRollingInputs,
    build_stateful_source_request,
    explicit_window_bounds,
    get_risk_free_coverage_details,
    resolve_stateful_rolling_inputs,
)


def _build_stateful_source_request(stateful: RollingStatefulInput) -> dict[str, Any]:
    return build_stateful_source_request(stateful)


def _explicit_window_bounds(source_payload: dict[str, Any]) -> tuple[date, date] | None:
    return explicit_window_bounds(source_payload)


async def _get_risk_free_coverage_details(
    *,
    core_client: LotusCoreClientProtocol,
    currency: str,
    start_date: date,
    end_date: date,
    correlation_id: str | None,
) -> dict[str, Any]:
    return await get_risk_free_coverage_details(
        core_client=core_client,
        currency=currency,
        start_date=start_date,
        end_date=end_date,
        correlation_id=correlation_id,
    )


def _build_stateless_request(
    stateful: RollingStatefulInput,
    *,
    portfolio_points: list[ReturnPoint],
    benchmark_points: list[ReturnPoint],
    risk_free_points: list[ReturnPoint],
) -> RollingStatelessInput:
    _validate_stateful_workload(
        stateful=stateful,
        portfolio_points=portfolio_points,
        benchmark_points=benchmark_points,
        risk_free_points=risk_free_points,
    )
    return RollingStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=portfolio_points,
        benchmark_returns=benchmark_points,
        risk_free_returns=risk_free_points,
        rolling_options=stateful.rolling_options,
    )


def _validate_stateful_workload(
    *,
    stateful: RollingStatefulInput,
    portfolio_points: list[ReturnPoint],
    benchmark_points: list[ReturnPoint],
    risk_free_points: list[ReturnPoint],
) -> None:
    max_sourced_observations = max(
        len(portfolio_points),
        len(benchmark_points),
        len(risk_free_points),
    )
    if max_sourced_observations > ROLLING_MAX_STATELESS_OBSERVATIONS:
        raise ValueError(
            "stateful rolling sourced return observations exceed supported maximum "
            f"{ROLLING_MAX_STATELESS_OBSERVATIONS}"
        )
    validate_rolling_time_series_workload(
        period_count=len(stateful.periods),
        window_count=len(stateful.rolling_options.window_lengths),
        observation_count=len(portfolio_points),
        include_time_series=stateful.rolling_options.include_time_series,
    )


def _attach_stateful_lineage(
    response: RollingResponse,
    *,
    include_risk_free: bool,
    source_payload: dict[str, Any],
    risk_free_request: dict[str, Any] | None,
) -> RollingResponse:
    dependency_services = ["lotus-performance"]
    if include_risk_free:
        dependency_services.append("lotus-core")
    response.metadata.source_services = ordered_source_services(*dependency_services)
    response.metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-performance",
        operation="/integration/returns/series",
        payload=source_payload,
    )
    if risk_free_request is not None:
        response.metadata.upstream_request_fingerprints.update(
            upstream_request_fingerprint(
                service="lotus-core",
                operation="/integration/reference/risk-free-series",
                payload=risk_free_request,
            )
        )
    return response


def _calculate_stateful_response(resolved_inputs: ResolvedStatefulRollingInputs) -> RollingResponse:
    stateless = _build_stateless_request(
        resolved_inputs.stateful,
        portfolio_points=resolved_inputs.portfolio_points,
        benchmark_points=resolved_inputs.benchmark_points,
        risk_free_points=resolved_inputs.risk_free_points,
    )
    return calculate_rolling_metrics(stateless, input_mode=RollingInputMode.STATEFUL)


async def calculate_rolling_metrics_stateful(
    stateful: RollingStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol | None = None,
    correlation_id: str | None,
) -> RollingResponse:
    resolved_inputs = await resolve_stateful_rolling_inputs(
        stateful,
        performance_client=performance_client,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    return _attach_stateful_lineage(
        _calculate_stateful_response(resolved_inputs),
        include_risk_free=resolved_inputs.include_risk_free,
        source_payload=resolved_inputs.source_payload,
        risk_free_request=resolved_inputs.risk_free_request,
    )
