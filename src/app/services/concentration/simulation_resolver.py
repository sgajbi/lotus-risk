from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationRequest,
    ConcentrationValuationContext,
    SimulationConcentrationInput,
)
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
    IssuerEntry,
    IssuerIdentity,
    PositionEntry,
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
from app.services.concentration.simulation_session import (
    SimulationSession,
    apply_simulation_changes,
    resolve_simulation_session,
    session_with_snapshot_version,
    simulation_snapshot_payload,
)


@dataclass(frozen=True)
class _SimulationSnapshotState:
    baseline_positions: list[PositionEntry]
    projected_positions: list[PositionEntry]
    baseline_issuers: list[IssuerEntry]
    projected_issuers: list[IssuerEntry]
    covered_baseline: int
    covered_projected: int
    total_baseline: int
    total_projected: int
    issuer_note: str | None
    valuation_context: ConcentrationValuationContext | None


def _issuer_map_from_snapshot_sections(
    request: ConcentrationRequest,
    *,
    sections: dict[str, Any],
    issuer_mappings: list[Any],
) -> tuple[dict[str, IssuerIdentity], str | None]:
    core_issuer_map, issuer_note = _extract_issuer_map(
        sections, grouping_level=request.issuer_grouping_level
    )
    _apply_snapshot_display_names(sections, core_issuer_map)
    caller_map = _caller_issuer_map(
        mappings=issuer_mappings,
        grouping_level=request.issuer_grouping_level,
    )
    return (
        _merge_issuer_maps(
            caller_map=caller_map,
            core_map=core_issuer_map,
            policy=request.enrichment_policy,
        ),
        issuer_note,
    )


def _simulation_snapshot_state(
    snapshot: dict[str, Any],
    *,
    sections: dict[str, Any],
    issuer_by_security: dict[str, IssuerIdentity],
    issuer_note: str | None,
) -> _SimulationSnapshotState:
    baseline_positions, baseline_issuers, covered_baseline, total_baseline = (
        _extract_values_with_issuer_from_snapshot(
            sections.get("positions_baseline"), issuer_by_security
        )
    )
    projected_positions, projected_issuers, covered_projected, total_projected = (
        _extract_values_with_issuer_from_snapshot(
            sections.get("positions_projected"), issuer_by_security
        )
    )
    if not projected_positions:
        projected_positions = baseline_positions
    if not projected_issuers:
        projected_issuers = baseline_issuers
        covered_projected = covered_baseline
        total_projected = total_baseline

    return _SimulationSnapshotState(
        baseline_positions=baseline_positions,
        projected_positions=projected_positions,
        baseline_issuers=baseline_issuers,
        projected_issuers=projected_issuers,
        covered_baseline=covered_baseline,
        covered_projected=covered_projected,
        total_baseline=total_baseline,
        total_projected=total_projected,
        issuer_note=issuer_note,
        valuation_context=_extract_valuation_context(snapshot.get("valuation_context")),
    )


def _simulation_metadata(
    request: ConcentrationRequest,
    *,
    simulation: SimulationConcentrationInput,
    session: SimulationSession,
    snapshot_payload: dict[str, Any],
) -> ConcentrationMetadata:
    metadata = build_metadata(
        request=request,
        as_of_date=simulation.as_of_date,
        portfolio_id=simulation.portfolio_id,
        simulation_session_id=session.session_id,
        simulation_session_version=session.version,
        session_expires_at=session.expires_at,
        include_cash_positions=simulation.include_cash_positions,
        include_zero_quantity_positions=simulation.include_zero_quantity_positions,
    )
    metadata.source_services = ordered_source_services("lotus-core")
    metadata.upstream_request_fingerprints = upstream_request_fingerprint(
        service="lotus-core",
        operation=f"/integration/portfolios/{simulation.portfolio_id}/core-snapshot",
        payload=snapshot_payload,
    )
    return metadata


async def _fetch_simulation_snapshot_state(
    *,
    request: ConcentrationRequest,
    simulation: SimulationConcentrationInput,
    session: SimulationSession,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    snapshot_payload: dict[str, Any],
) -> tuple[_SimulationSnapshotState, SimulationSession]:
    snapshot = await core_client.get_core_snapshot(
        portfolio_id=simulation.portfolio_id,
        request_payload=snapshot_payload,
        correlation_id=correlation_id,
    )
    sections = snapshot.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("lotus-core simulation snapshot missing sections payload")

    issuer_by_security, issuer_note = _issuer_map_from_snapshot_sections(
        request=request,
        sections=sections,
        issuer_mappings=simulation.issuer_mappings,
    )
    return (
        _simulation_snapshot_state(
            snapshot,
            sections=sections,
            issuer_by_security=issuer_by_security,
            issuer_note=issuer_note,
        ),
        session_with_snapshot_version(session, snapshot=snapshot),
    )


def _simulation_computation_input(
    *,
    simulation: SimulationConcentrationInput,
    snapshot_state: _SimulationSnapshotState,
    metadata: ConcentrationMetadata,
) -> ConcentrationComputationInput:
    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.SIMULATION,
        current_positions=snapshot_state.baseline_positions,
        proposed_positions=snapshot_state.projected_positions,
        top_n=simulation.top_n,
        current_issuers=snapshot_state.baseline_issuers,
        proposed_issuers=snapshot_state.projected_issuers,
        covered_position_count_current=snapshot_state.covered_baseline,
        covered_position_count_proposed=snapshot_state.covered_projected,
        total_position_count_current=snapshot_state.total_baseline,
        total_position_count_proposed=snapshot_state.total_projected,
        issuer_note=snapshot_state.issuer_note,
        valuation_context=snapshot_state.valuation_context,
        metadata=metadata,
    )


async def resolve_simulation(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    actor_id: str | None,
) -> ConcentrationComputationInput:
    simulation = request.simulation_input
    if simulation is None:
        raise ValueError("simulation_input is required when input_mode=simulation")

    session = await resolve_simulation_session(
        simulation,
        core_client=core_client,
        correlation_id=correlation_id,
        actor_id=actor_id,
    )
    session = await apply_simulation_changes(
        simulation,
        session=session,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    snapshot_payload = simulation_snapshot_payload(simulation, session=session)
    snapshot_state, session = await _fetch_simulation_snapshot_state(
        request=request,
        simulation=simulation,
        session=session,
        core_client=core_client,
        correlation_id=correlation_id,
        snapshot_payload=snapshot_payload,
    )
    metadata = _simulation_metadata(
        request,
        simulation=simulation,
        session=session,
        snapshot_payload=snapshot_payload,
    )
    return _simulation_computation_input(
        simulation=simulation,
        snapshot_state=snapshot_state,
        metadata=metadata,
    )
