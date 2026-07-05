from __future__ import annotations

from typing import Any

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationRequest,
    SimulationConcentrationInput,
)
from app.services.audit_lineage import ordered_source_services, upstream_request_fingerprint
from app.services.concentration.datamodels import ConcentrationComputationInput
from app.services.concentration.metadata import build_metadata
from app.services.concentration.ports import LotusCoreClientProtocol
from app.services.concentration.simulation_snapshot import (
    SimulationSnapshotState,
    issuer_map_from_snapshot_sections,
    simulation_snapshot_state,
)
from app.services.concentration.simulation_session import (
    SimulationSession,
    apply_simulation_changes,
    resolve_simulation_session,
    session_with_snapshot_version,
    simulation_snapshot_payload,
)
from app.services.concentration.upstream_contracts import invalid_core_snapshot_payload


def _simulation_metadata(
    request: ConcentrationRequest,
    *,
    simulation: SimulationConcentrationInput,
    session: SimulationSession,
    correlation_id: str | None,
    snapshot_payload: dict[str, Any],
) -> ConcentrationMetadata:
    metadata = build_metadata(
        request=request,
        as_of_date=simulation.as_of_date,
        portfolio_id=simulation.portfolio_id,
        correlation_id=correlation_id,
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
) -> tuple[SimulationSnapshotState, SimulationSession]:
    snapshot = await core_client.get_core_snapshot(
        portfolio_id=simulation.portfolio_id,
        request_payload=snapshot_payload,
        correlation_id=correlation_id,
    )
    sections = snapshot.get("sections")
    if not isinstance(sections, dict):
        raise invalid_core_snapshot_payload(
            snapshot_mode="SIMULATION",
            reason="missing_sections",
        )

    issuer_by_security, issuer_note = issuer_map_from_snapshot_sections(
        request=request,
        sections=sections,
        issuer_mappings=simulation.issuer_mappings,
    )
    return (
        simulation_snapshot_state(
            snapshot,
            sections=sections,
            issuer_by_security=issuer_by_security,
            issuer_note=issuer_note,
        ),
        session_with_snapshot_version(session, snapshot=snapshot),
    )


async def _resolve_applied_simulation_session(
    *,
    simulation: SimulationConcentrationInput,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    actor_id: str | None,
) -> SimulationSession:
    session = await resolve_simulation_session(
        simulation,
        core_client=core_client,
        correlation_id=correlation_id,
        actor_id=actor_id,
    )
    return await apply_simulation_changes(
        simulation,
        session=session,
        core_client=core_client,
        correlation_id=correlation_id,
    )


def _simulation_computation_input(
    *,
    simulation: SimulationConcentrationInput,
    snapshot_state: SimulationSnapshotState,
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
        use_current_state_when_proposed_empty=False,
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

    session = await _resolve_applied_simulation_session(
        simulation=simulation,
        core_client=core_client,
        correlation_id=correlation_id,
        actor_id=actor_id,
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
        correlation_id=correlation_id,
        snapshot_payload=snapshot_payload,
    )
    return _simulation_computation_input(
        simulation=simulation,
        snapshot_state=snapshot_state,
        metadata=metadata,
    )
