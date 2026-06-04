from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationRequest,
    EnrichmentPolicy,
    IssuerGroupingLevel,
    SimulationConcentrationInput,
    ConcentrationValuationContext,
    StatefulConcentrationInput,
)
from app.services.audit_lineage import (
    ordered_source_services,
    upstream_request_fingerprint,
)
from app.service_metadata import SERVICE_NAME
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
    IssuerEntry,
    IssuerIdentity,
    PositionEntry,
)
from app.services.concentration.metadata import build_metadata
from app.services.concentration.parsing import (
    _as_datetime,
    _as_int,
    _as_str,
    _apply_snapshot_display_names,
    _caller_issuer_map,
    _extract_issuer_map,
    _extract_valuation_context,
    _extract_values_with_issuer_from_snapshot,
    _merge_issuer_maps,
)
from app.services.concentration.ports import LotusCoreClientProtocol


@dataclass(frozen=True)
class _SimulationSession:
    session_id: str
    version: int | None
    expires_at: datetime | None


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


async def _resolve_simulation_session(
    simulation: SimulationConcentrationInput,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    actor_id: str | None,
) -> _SimulationSession:
    session_id = simulation.session_id
    session_version: int | None = None
    session_expires_at: datetime | None = None

    should_create_session = simulation.start_new_session or not session_id
    if should_create_session:
        session_response = await core_client.create_simulation_session(
            portfolio_id=simulation.portfolio_id,
            ttl_hours=simulation.session_ttl_hours,
            created_by=actor_id or SERVICE_NAME,
            correlation_id=correlation_id,
        )
        session_record = session_response.get("session")
        if not isinstance(session_record, dict):
            raise ValueError(
                "lotus-core create simulation session returned invalid response payload"
            )
        resolved_session_id = _as_str(session_record.get("session_id"))
        if not resolved_session_id:
            raise ValueError("lotus-core create simulation session response missing session_id")
        session_id = resolved_session_id
        session_version = _as_int(session_record.get("version"))
        session_expires_at = _as_datetime(session_record.get("expires_at"))

    if session_id is None:
        raise ValueError("simulation session_id could not be resolved")
    return _SimulationSession(
        session_id=session_id,
        version=session_version,
        expires_at=session_expires_at,
    )


async def _apply_simulation_changes(
    simulation: SimulationConcentrationInput,
    *,
    session: _SimulationSession,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> _SimulationSession:
    if not simulation.simulation_changes:
        return session

    payload = [
        change.model_dump(mode="json", exclude_none=True)
        for change in simulation.simulation_changes
    ]
    changes_response = await core_client.add_simulation_changes(
        session_id=session.session_id,
        changes=payload,
        correlation_id=correlation_id,
    )
    session_version = _as_int(changes_response.get("version")) or session.version
    return _SimulationSession(
        session_id=session.session_id,
        version=session_version,
        expires_at=session.expires_at,
    )


def _simulation_snapshot_payload(
    simulation: SimulationConcentrationInput,
    *,
    session: _SimulationSession,
) -> dict[str, Any]:
    expected_version = simulation.expected_version or session.version
    snapshot_payload: dict[str, Any] = {
        "as_of_date": simulation.as_of_date.isoformat(),
        "snapshot_mode": "SIMULATION",
        "sections": [
            "positions_baseline",
            "positions_projected",
            "positions_delta",
            "portfolio_totals",
            "instrument_enrichment",
        ],
        "simulation": {
            "session_id": session.session_id,
        },
        "options": {
            "include_zero_quantity_positions": simulation.include_zero_quantity_positions,
            "include_cash_positions": simulation.include_cash_positions,
            "position_basis": "market_value_base",
            "weight_basis": "total_market_value_base",
        },
    }
    if expected_version is not None:
        snapshot_payload["simulation"]["expected_version"] = expected_version
    if simulation.reporting_currency:
        snapshot_payload["reporting_currency"] = simulation.reporting_currency
    return snapshot_payload


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


def _session_with_snapshot_version(
    session: _SimulationSession,
    *,
    snapshot: dict[str, Any],
) -> _SimulationSession:
    snapshot_simulation = snapshot.get("simulation")
    if not isinstance(snapshot_simulation, dict):
        return session
    return _SimulationSession(
        session_id=session.session_id,
        version=_as_int(snapshot_simulation.get("version")) or session.version,
        expires_at=session.expires_at,
    )


def _simulation_metadata(
    request: ConcentrationRequest,
    *,
    simulation: SimulationConcentrationInput,
    session: _SimulationSession,
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
    session: _SimulationSession,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
    snapshot_payload: dict[str, Any],
) -> tuple[_SimulationSnapshotState, _SimulationSession]:
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
        _session_with_snapshot_version(session, snapshot=snapshot),
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

    session = await _resolve_simulation_session(
        simulation,
        core_client=core_client,
        correlation_id=correlation_id,
        actor_id=actor_id,
    )
    session = await _apply_simulation_changes(
        simulation,
        session=session,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    snapshot_payload = _simulation_snapshot_payload(simulation, session=session)
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
