from __future__ import annotations

from typing import Any

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationMetadata,
    ConcentrationRequest,
    StatefulConcentrationInput,
)
from app.services.audit_lineage import (
    ordered_source_services,
    upstream_request_fingerprint,
)
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
)
from app.services.concentration.metadata import build_metadata
from app.services.concentration.ports import LotusCoreClientProtocol
from app.services.concentration.simulation_resolver import (
    resolve_simulation as _resolve_simulation,
)
from app.services.concentration.stateful_snapshot import (
    StatefulBaselineValues,
    StatefulSnapshotState,
    fetch_stateful_snapshot_state,
    stateful_baseline_values,
    stateful_snapshot_payload,
)


async def resolve_stateful(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol,
    correlation_id: str | None,
) -> ConcentrationComputationInput:
    stateful = request.stateful_input
    if stateful is None:
        raise ValueError("stateful_input is required when input_mode=stateful")

    snapshot_payload = stateful_snapshot_payload(stateful)
    snapshot_state = await fetch_stateful_snapshot_state(
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
    baseline = stateful_baseline_values(snapshot_state)
    return _stateful_computation_input(
        stateful=stateful,
        snapshot_state=snapshot_state,
        metadata=metadata,
        baseline=baseline,
    )


def _stateful_computation_input(
    *,
    stateful: StatefulConcentrationInput,
    snapshot_state: StatefulSnapshotState,
    metadata: ConcentrationMetadata,
    baseline: StatefulBaselineValues,
) -> ConcentrationComputationInput:
    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.STATEFUL,
        current_positions=baseline.positions,
        proposed_positions=baseline.positions,
        top_n=stateful.top_n,
        current_issuers=baseline.issuers,
        proposed_issuers=baseline.issuers,
        covered_position_count_current=baseline.covered_position_count,
        covered_position_count_proposed=baseline.covered_position_count,
        total_position_count_current=baseline.total_position_count,
        total_position_count_proposed=baseline.total_position_count,
        issuer_note=snapshot_state.issuer_note,
        valuation_context=snapshot_state.valuation_context,
        metadata=metadata,
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
