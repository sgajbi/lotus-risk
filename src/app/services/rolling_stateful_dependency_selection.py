from __future__ import annotations

from dataclasses import dataclass

from app.contracts.downstream_authority import DownstreamAuthority
from app.contracts.rolling import ROLLING_BENCHMARK_METRICS, RollingStatefulInput
from app.services.core_portfolio_currency import resolve_portfolio_reporting_currency
from app.services.rolling_metric_series import ROLLING_SHARPE_METRIC
from app.services.rolling_stateful_models import LotusCoreClientProtocol


@dataclass(frozen=True)
class RollingStatefulDependencySelection:
    stateful: RollingStatefulInput
    include_risk_free: bool
    reporting_currency: str | None
    core_snapshot_request: dict[str, object] | None


def requires_risk_free(stateful: RollingStatefulInput) -> bool:
    return ROLLING_SHARPE_METRIC in stateful.rolling_options.metrics


def requires_benchmark(stateful: RollingStatefulInput) -> bool:
    return any(metric in ROLLING_BENCHMARK_METRICS for metric in stateful.rolling_options.metrics)


async def resolve_stateful_dependency_selection(
    stateful: RollingStatefulInput,
    *,
    core_client: LotusCoreClientProtocol | None,
    authority: DownstreamAuthority,
) -> RollingStatefulDependencySelection:
    include_risk_free = requires_risk_free(stateful)
    resolved = await resolve_portfolio_reporting_currency(
        portfolio_id=stateful.portfolio_id,
        as_of_date=stateful.as_of_date,
        requested_currency=stateful.reporting_currency,
        requires_risk_free=include_risk_free,
        core_client=core_client,
        authority=authority,
    )
    if resolved.reporting_currency != stateful.reporting_currency:
        stateful = stateful.model_copy(update={"reporting_currency": resolved.reporting_currency})
    return RollingStatefulDependencySelection(
        stateful=stateful,
        include_risk_free=include_risk_free,
        reporting_currency=resolved.reporting_currency,
        core_snapshot_request=resolved.snapshot_request,
    )


__all__ = [
    "RollingStatefulDependencySelection",
    "requires_benchmark",
    "requires_risk_free",
    "resolve_stateful_dependency_selection",
]
