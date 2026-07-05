from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.concentration import (
    ConcentrationRequest,
    ConcentrationValuationContext,
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
from app.services.concentration.upstream_contracts import invalid_core_snapshot_payload


@dataclass(frozen=True)
class SimulationSnapshotState:
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


def issuer_map_from_snapshot_sections(
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


def simulation_snapshot_state(
    snapshot: dict[str, Any],
    *,
    sections: dict[str, Any],
    issuer_by_security: dict[str, IssuerIdentity],
    issuer_note: str | None,
) -> SimulationSnapshotState:
    raw_projected_positions = sections.get("positions_projected")
    if "positions_projected" not in sections:
        raise invalid_core_snapshot_payload(
            snapshot_mode="SIMULATION",
            reason="missing_positions_projected",
        )
    if not isinstance(raw_projected_positions, list):
        raise invalid_core_snapshot_payload(
            snapshot_mode="SIMULATION",
            reason="invalid_positions_projected",
        )
    baseline_positions, baseline_issuers, covered_baseline, total_baseline = (
        _extract_values_with_issuer_from_snapshot(
            sections.get("positions_baseline"), issuer_by_security
        )
    )
    projected_positions, projected_issuers, covered_projected, total_projected = (
        _extract_values_with_issuer_from_snapshot(raw_projected_positions, issuer_by_security)
    )

    return SimulationSnapshotState(
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


__all__ = [
    "SimulationSnapshotState",
    "issuer_map_from_snapshot_sections",
    "simulation_snapshot_state",
]
