from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationRequest,
    EnrichmentPolicy,
    IssuerGroupingLevel,
    ConcentrationValuationContext,
    StatefulConcentrationInput,
)
from app.services.audit_lineage import (
    ordered_source_services,
    upstream_request_fingerprint,
)
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
    IssuerIdentity,
)
from app.services.concentration.metadata import build_metadata
from app.services.concentration.parsing import (
    _apply_snapshot_display_names,
    _caller_issuer_map,
    _extract_issuer_map,
    _extract_valuation_context,
    _extract_values_with_issuer_from_snapshot,
    _merge_issuer_maps,
)
from app.services.concentration.ports import LotusCoreClientProtocol
from app.services.concentration.simulation_resolver import (
    resolve_simulation as _resolve_simulation,
)


@dataclass(frozen=True)
class _StatefulSnapshotState:
    sections: dict[str, Any]
    issuer_by_security: dict[str, IssuerIdentity]
    issuer_note: str | None
    valuation_context: ConcentrationValuationContext | None


async def resolve_stateful(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> ConcentrationComputationInput:
    stateful = request.stateful_input
    if stateful is None:
        raise ValueError("stateful_input is required when input_mode=stateful")

    snapshot_payload = _stateful_snapshot_payload(stateful)
    snapshot_state = await _fetch_stateful_snapshot_state(
        request=request,
        stateful=stateful,
        core_client=core_client,
        correlation_id=correlation_id,
        snapshot_payload=snapshot_payload,
    )
    metadata = _stateful_metadata(
        request=request,
        stateful=stateful,
        snapshot_payload=snapshot_payload,
    )
    baseline_positions, baseline_issuers, covered_baseline, total_baseline = (
        _extract_values_with_issuer_from_snapshot(
            snapshot_state.sections.get("positions_baseline"),
            snapshot_state.issuer_by_security,
        )
    )

    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.STATEFUL,
        current_positions=baseline_positions,
        proposed_positions=baseline_positions,
        top_n=stateful.top_n,
        current_issuers=baseline_issuers,
        proposed_issuers=baseline_issuers,
        covered_position_count_current=covered_baseline,
        covered_position_count_proposed=covered_baseline,
        total_position_count_current=total_baseline,
        total_position_count_proposed=total_baseline,
        issuer_note=snapshot_state.issuer_note,
        valuation_context=snapshot_state.valuation_context,
        metadata=metadata,
    )


def _stateful_snapshot_payload(stateful: StatefulConcentrationInput) -> dict[str, Any]:
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


async def _fetch_stateful_snapshot_state(
    *,
    request: ConcentrationRequest,
    stateful: StatefulConcentrationInput,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    snapshot_payload: dict[str, Any],
) -> _StatefulSnapshotState:
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
    issuer_by_security = _stateful_issuer_map(
        stateful=stateful,
        core_map=core_issuer_map,
        grouping_level=request.issuer_grouping_level,
        enrichment_policy=request.enrichment_policy,
    )
    return _StatefulSnapshotState(
        sections=sections,
        issuer_by_security=issuer_by_security,
        issuer_note=issuer_note,
        valuation_context=_extract_valuation_context(snapshot.get("valuation_context")),
    )


def _stateful_issuer_map(
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


def _stateful_metadata(
    *,
    request: ConcentrationRequest,
    stateful: StatefulConcentrationInput,
    snapshot_payload: dict[str, Any],
) -> ConcentrationMetadata:
    metadata = build_metadata(
        request=request,
        as_of_date=stateful.as_of_date,
        portfolio_id=stateful.portfolio_id,
        include_cash_positions=stateful.include_cash_positions,
        include_zero_quantity_positions=stateful.include_zero_quantity_positions,
    )
    metadata.source_services = ordered_source_services("lotus-core")
    metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-core",
        operation=f"/integration/portfolios/{stateful.portfolio_id}/core-snapshot",
        payload=snapshot_payload,
    )
    return metadata


async def resolve_simulation(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    actor_id: str | None,
) -> ConcentrationComputationInput:
    return await _resolve_simulation(
        request,
        core_client=core_client,
        correlation_id=correlation_id,
        actor_id=actor_id,
    )
