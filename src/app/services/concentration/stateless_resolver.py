from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from collections.abc import Sequence

from app.contracts.concentration import (
    ConcentrationInputMode,
    ConcentrationRequest,
    EnrichmentPolicy,
    IssuerGroupingLevel,
)
from app.services.concentration.datamodels import (
    ConcentrationComputationInput,
    IssuerEntry,
    IssuerIdentity,
    PositionEntry,
)
from app.services.concentration.metadata import build_metadata
from app.services.concentration.parsing import (
    _as_str,
    _extract_values_from_stateless_payload,
    _issuer_key_from_position,
    _merge_issuer_maps,
    _to_weighted_values,
)
from app.services.concentration.ports import LotusCoreClientProtocol


@dataclass(frozen=True)
class _WeightedConcentrationState:
    current_positions: list[PositionEntry]
    proposed_positions: list[PositionEntry]
    current_issuers: list[IssuerEntry]
    proposed_issuers: list[IssuerEntry]
    covered_current: int
    covered_proposed: int
    total_current: int
    total_proposed: int
    issuer_note: str | None


def _stateless_caller_issuer_map(
    request: ConcentrationRequest,
) -> dict[str, IssuerIdentity]:
    stateless_input = request.stateless_input
    if stateless_input is None:
        raise ValueError("stateless_input is required when input_mode=stateless")

    caller_issuer_map: dict[str, IssuerIdentity] = {}
    positions = cast(
        Sequence[Any],
        [*stateless_input.current_positions, *stateless_input.projected_positions],
    )
    for position in positions:
        issuer_key = _issuer_key_from_position(
            issuer_id=position.issuer_id,
            issuer_name=None,
            ultimate_parent_issuer_id=position.ultimate_parent_issuer_id,
            ultimate_parent_issuer_name=None,
            grouping_level=request.issuer_grouping_level,
        )
        if issuer_key:
            caller_issuer_map[position.security_id] = issuer_key
    return caller_issuer_map


def _stateless_security_ids(
    rows: Sequence[PositionEntry],
) -> list[str]:
    return sorted({row.security_id for row in rows if row.security_id is not None})


def _issuer_map_from_core_records(
    records: list[Any],
    *,
    grouping_level: IssuerGroupingLevel,
) -> dict[str, IssuerIdentity]:
    core_issuer_map: dict[str, IssuerIdentity] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        security_id = _as_str(record.get("security_id"))
        if not security_id:
            continue
        if grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
            issuer_id = _as_str(record.get("ultimate_parent_issuer_id")) or _as_str(
                record.get("issuer_id")
            )
            issuer_name = _as_str(record.get("ultimate_parent_issuer_name")) or _as_str(
                record.get("issuer_name")
            )
        else:
            issuer_id = _as_str(record.get("issuer_id"))
            issuer_name = _as_str(record.get("issuer_name"))
        if issuer_id:
            core_issuer_map[security_id] = IssuerIdentity(
                issuer_id=issuer_id,
                issuer_name=issuer_name,
            )
    return core_issuer_map


async def _stateless_core_issuer_map(
    request: ConcentrationRequest,
    *,
    rows: Sequence[PositionEntry],
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> tuple[dict[str, IssuerIdentity], str | None]:
    if request.enrichment_policy == EnrichmentPolicy.USE_CALLER_ONLY or core_client is None:
        return {}, None

    security_ids = _stateless_security_ids(rows)
    if not security_ids:
        return {}, None

    try:
        enrichment_payload = await core_client.get_instrument_enrichment(
            security_ids=security_ids,
            correlation_id=correlation_id,
        )
    except ValueError:
        return {}, "lotus-core enrichment unavailable for stateless issuer mapping"

    records = enrichment_payload.get("records")
    if not isinstance(records, list):
        return {}, "lotus-core enrichment payload missing records list"
    return (
        _issuer_map_from_core_records(records, grouping_level=request.issuer_grouping_level),
        None,
    )


def _weighted_stateless_state(
    *,
    current_rows: list[PositionEntry],
    proposed_rows: list[PositionEntry],
    issuer_by_security: dict[str, IssuerIdentity],
    issuer_note: str | None,
) -> _WeightedConcentrationState:
    current_positions, current_issuers, covered_current, total_current = _to_weighted_values(
        current_rows,
        issuer_by_security=issuer_by_security,
    )
    proposed_positions, proposed_issuers, covered_proposed, total_proposed = _to_weighted_values(
        proposed_rows,
        issuer_by_security=issuer_by_security,
    )
    if (
        issuer_note is None
        and (total_current > 0 or total_proposed > 0)
        and (covered_current == 0 and covered_proposed == 0)
    ):
        issuer_note = "issuer mapping unavailable for stateless payload"

    return _WeightedConcentrationState(
        current_positions=current_positions,
        proposed_positions=proposed_positions if proposed_positions else current_positions,
        current_issuers=current_issuers,
        proposed_issuers=proposed_issuers if proposed_issuers else current_issuers,
        covered_current=covered_current,
        covered_proposed=covered_proposed if proposed_positions else covered_current,
        total_current=total_current,
        total_proposed=total_proposed if proposed_positions else total_current,
        issuer_note=issuer_note,
    )


async def resolve_stateless(
    request: ConcentrationRequest,
    *,
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> ConcentrationComputationInput:
    stateless_input = request.stateless_input
    if stateless_input is None:
        raise ValueError("stateless_input is required when input_mode=stateless")

    current_rows, proposed_rows = _extract_values_from_stateless_payload(stateless_input)
    all_rows = [*current_rows, *proposed_rows]
    core_issuer_map, issuer_note = await _stateless_core_issuer_map(
        request,
        rows=all_rows,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    issuer_by_security = _merge_issuer_maps(
        caller_map=_stateless_caller_issuer_map(request),
        core_map=core_issuer_map,
        policy=request.enrichment_policy,
    )
    weighted_state = _weighted_stateless_state(
        current_rows=current_rows,
        proposed_rows=proposed_rows,
        issuer_by_security=issuer_by_security,
        issuer_note=issuer_note,
    )

    return ConcentrationComputationInput(
        input_mode=ConcentrationInputMode.STATELESS,
        current_positions=weighted_state.current_positions,
        proposed_positions=weighted_state.proposed_positions,
        top_n=stateless_input.top_n,
        current_issuers=weighted_state.current_issuers,
        proposed_issuers=weighted_state.proposed_issuers,
        covered_position_count_current=weighted_state.covered_current,
        covered_position_count_proposed=weighted_state.covered_proposed,
        total_position_count_current=weighted_state.total_current,
        total_position_count_proposed=weighted_state.total_proposed,
        issuer_note=weighted_state.issuer_note,
        metadata=build_metadata(
            request=request,
            include_cash_positions=None,
            include_zero_quantity_positions=None,
        ),
    )
