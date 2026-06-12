from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.concentration import (
    ConcentrationRequest,
    ConcentrationValuationContext,
    EnrichmentPolicy,
    IssuerGroupingLevel,
    StatefulConcentrationInput,
)
from app.services.concentration.datamodels import (
    IssuerEntry,
    IssuerIdentity,
    PositionEntry,
)
from app.services.concentration.parsing import (
    _apply_snapshot_display_names,
    _caller_issuer_map,
    _extract_issuer_map,
    _extract_valuation_context,
    _extract_values_with_issuer_from_snapshot,
    _merge_issuer_maps,
)
from app.services.concentration.ports import LotusCoreClientProtocol


@dataclass(frozen=True)
class StatefulSnapshotState:
    sections: dict[str, Any]
    issuer_by_security: dict[str, IssuerIdentity]
    issuer_note: str | None
    valuation_context: ConcentrationValuationContext | None


@dataclass(frozen=True)
class StatefulBaselineValues:
    positions: list[PositionEntry]
    issuers: list[IssuerEntry]
    covered_position_count: int
    total_position_count: int


def stateful_snapshot_payload(stateful: StatefulConcentrationInput) -> dict[str, Any]:
    snapshot_payload: dict[str, Any] = {
        "as_of_date": stateful.as_of_date.isoformat(),
        "snapshot_mode": "BASELINE",
        "sections": ["positions_baseline", "portfolio_totals", "instrument_enrichment"],
        "options": {
            "include_zero_quantity_positions": stateful.include_zero_quantity_positions,
            "include_cash_positions": stateful.include_cash_positions,
            "position_basis": "market_value_base",
            "weight_basis": "total_market_value_base",
        },
    }
    if stateful.reporting_currency:
        snapshot_payload["reporting_currency"] = stateful.reporting_currency
    return snapshot_payload


async def fetch_stateful_snapshot_state(
    *,
    request: ConcentrationRequest,
    stateful: StatefulConcentrationInput,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    snapshot_payload: dict[str, Any],
) -> StatefulSnapshotState:
    snapshot = await core_client.get_core_snapshot(
        portfolio_id=stateful.portfolio_id,
        request_payload=snapshot_payload,
        correlation_id=correlation_id,
    )
    sections = snapshot.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("lotus-core stateful snapshot missing sections payload")

    core_issuer_map, issuer_note = _extract_issuer_map(
        sections, grouping_level=request.issuer_grouping_level
    )
    _apply_snapshot_display_names(sections, core_issuer_map)
    issuer_by_security = stateful_issuer_map(
        stateful=stateful,
        core_map=core_issuer_map,
        grouping_level=request.issuer_grouping_level,
        enrichment_policy=request.enrichment_policy,
    )
    return StatefulSnapshotState(
        sections=sections,
        issuer_by_security=issuer_by_security,
        issuer_note=issuer_note,
        valuation_context=_extract_valuation_context(snapshot.get("valuation_context")),
    )


def stateful_baseline_values(
    snapshot_state: StatefulSnapshotState,
) -> StatefulBaselineValues:
    positions, issuers, covered_count, total_count = _extract_values_with_issuer_from_snapshot(
        snapshot_state.sections.get("positions_baseline"),
        snapshot_state.issuer_by_security,
    )
    return StatefulBaselineValues(
        positions=positions,
        issuers=issuers,
        covered_position_count=covered_count,
        total_position_count=total_count,
    )


def stateful_issuer_map(
    *,
    stateful: StatefulConcentrationInput,
    core_map: dict[str, IssuerIdentity],
    grouping_level: IssuerGroupingLevel,
    enrichment_policy: EnrichmentPolicy,
) -> dict[str, IssuerIdentity]:
    caller_map = _caller_issuer_map(
        mappings=stateful.issuer_mappings,
        grouping_level=grouping_level,
    )
    return _merge_issuer_maps(
        caller_map=caller_map,
        core_map=core_map,
        policy=enrichment_policy,
    )


__all__ = [
    "StatefulBaselineValues",
    "StatefulSnapshotState",
    "fetch_stateful_snapshot_state",
    "stateful_baseline_values",
    "stateful_issuer_map",
    "stateful_snapshot_payload",
]
