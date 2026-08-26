from __future__ import annotations

from dataclasses import dataclass

from app.contracts.rolling import ROLLING_BENCHMARK_METRICS, RollingStatefulInput
from app.services.rolling_metric_series import ROLLING_SHARPE_METRIC
from app.services.rolling_stateful_models import LotusCoreClientProtocol


@dataclass(frozen=True)
class RollingStatefulDependencySelection:
    stateful: RollingStatefulInput
    include_risk_free: bool
    reporting_currency: str | None


def requires_risk_free(stateful: RollingStatefulInput) -> bool:
    return ROLLING_SHARPE_METRIC in stateful.rolling_options.metrics


def requires_benchmark(stateful: RollingStatefulInput) -> bool:
    return any(metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics)


async def _resolve_reporting_currency(
    *,
    stateful: RollingStatefulInput,
    include_risk_free: bool,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> str | None:
    if stateful.reporting_currency:
        return stateful.reporting_currency
    if not include_risk_free:
        return None
    if core_client is None:
        raise ValueError(
            "reporting_currency is required for rolling Sharpe in stateful mode when lotus-core is unavailable"
        )

    snapshot = await core_client.get_core_snapshot(
        portfolio_id=stateful.portfolio_id,
        request_payload={
            "snapshot_mode": "BASELINE",
            "as_of_date": stateful.as_of_date.isoformat(),
            "sections": ["portfolio_totals"],
        },
        correlation_id=correlation_id,
    )
    valuation_context = snapshot.get("valuation_context")
    if not isinstance(valuation_context, dict):
        # The upstream JSON value violates its domain contract; this is not a caller type error.
        raise ValueError(  # noqa: TRY004
            "lotus-core core-snapshot payload missing valuation_context"
        )
    resolved_reporting_currency = valuation_context.get("reporting_currency")
    if not isinstance(resolved_reporting_currency, str) or not resolved_reporting_currency:
        resolved_reporting_currency = valuation_context.get("portfolio_currency")
    if not isinstance(resolved_reporting_currency, str) or not resolved_reporting_currency:
        raise ValueError(
            "lotus-core core-snapshot payload missing portfolio/reporting currency required for rolling Sharpe"
        )
    return resolved_reporting_currency


async def resolve_stateful_dependency_selection(
    stateful: RollingStatefulInput,
    *,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> RollingStatefulDependencySelection:
    include_risk_free = requires_risk_free(stateful)
    resolved_reporting_currency = await _resolve_reporting_currency(
        stateful=stateful,
        include_risk_free=include_risk_free,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    if resolved_reporting_currency != stateful.reporting_currency:
        stateful = stateful.model_copy(update={"reporting_currency": resolved_reporting_currency})
    return RollingStatefulDependencySelection(
        stateful=stateful,
        include_risk_free=include_risk_free,
        reporting_currency=resolved_reporting_currency,
    )


__all__ = [
    "RollingStatefulDependencySelection",
    "requires_benchmark",
    "requires_risk_free",
    "resolve_stateful_dependency_selection",
]
