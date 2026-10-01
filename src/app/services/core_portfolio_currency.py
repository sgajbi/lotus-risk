"""Resolve omitted risk-free currency from the tenant-admitted Core portfolio snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.contracts.downstream_authority import DownstreamAuthority
from app.integrations.upstream_operations import LOTUS_CORE_SNAPSHOT_OPERATION
from app.upstream_errors import invalid_upstream_payload


class CoreSnapshotClient(Protocol):
    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ResolvedPortfolioCurrency:
    reporting_currency: str | None
    snapshot_request: dict[str, Any] | None


def _currency(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


async def resolve_portfolio_reporting_currency(
    *,
    portfolio_id: str,
    as_of_date: date,
    requested_currency: str | None,
    requires_risk_free: bool,
    core_client: CoreSnapshotClient | None,
    authority: DownstreamAuthority,
) -> ResolvedPortfolioCurrency:
    if requested_currency or not requires_risk_free:
        return ResolvedPortfolioCurrency(requested_currency, None)
    if core_client is None:
        raise ValueError("lotus-core client is required for stateful risk-free sourcing")

    snapshot_request: dict[str, Any] = {
        "snapshot_mode": "BASELINE",
        "as_of_date": as_of_date.isoformat(),
        "sections": ["portfolio_totals"],
    }
    snapshot = await core_client.get_core_snapshot(
        portfolio_id=portfolio_id,
        request_payload=snapshot_request,
        authority=authority,
    )
    context = snapshot.get("valuation_context") if isinstance(snapshot, dict) else None
    if not isinstance(context, dict):
        raise invalid_upstream_payload(
            service="lotus-core",
            operation=LOTUS_CORE_SNAPSHOT_OPERATION,
            message="lotus-core core-snapshot missing valuation context for risk-free currency",
        )
    currency = _currency(context.get("reporting_currency")) or _currency(
        context.get("portfolio_currency")
    )
    if currency is None:
        raise invalid_upstream_payload(
            service="lotus-core",
            operation=LOTUS_CORE_SNAPSHOT_OPERATION,
            message="lotus-core core-snapshot missing portfolio/reporting currency",
        )
    return ResolvedPortfolioCurrency(currency, snapshot_request)
