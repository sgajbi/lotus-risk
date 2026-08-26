from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from app.contracts.concentration import (
    ConcentrationRequest,
    EnrichmentPolicy,
    IssuerGroupingLevel,
)
from app.services.concentration.datamodels import IssuerIdentity, PositionEntry
from app.services.concentration.parsing import (
    _as_str,
    _issuer_key_from_position,
    _merge_issuer_maps,
)
from app.services.concentration.ports import LotusCoreClientProtocol


def stateless_caller_issuer_map(
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


def stateless_security_ids(
    rows: Sequence[PositionEntry],
) -> list[str]:
    return sorted({row.security_id for row in rows if row.security_id is not None})


def issuer_map_from_core_records(
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


async def stateless_core_issuer_map(
    request: ConcentrationRequest,
    *,
    rows: Sequence[PositionEntry],
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> tuple[dict[str, IssuerIdentity], str | None]:
    if request.enrichment_policy == EnrichmentPolicy.USE_CALLER_ONLY or core_client is None:
        return {}, None

    security_ids = stateless_security_ids(rows)
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
        issuer_map_from_core_records(records, grouping_level=request.issuer_grouping_level),
        None,
    )


async def stateless_issuer_map(
    request: ConcentrationRequest,
    *,
    rows: Sequence[PositionEntry],
    core_client: LotusCoreClientProtocol | None,
    correlation_id: str | None,
) -> tuple[dict[str, IssuerIdentity], str | None]:
    core_issuer_map, issuer_note = await stateless_core_issuer_map(
        request,
        rows=rows,
        core_client=core_client,
        correlation_id=correlation_id,
    )
    issuer_by_security = _merge_issuer_maps(
        caller_map=stateless_caller_issuer_map(request),
        core_map=core_issuer_map,
        policy=request.enrichment_policy,
    )
    return issuer_by_security, issuer_note


__all__ = [
    "issuer_map_from_core_records",
    "stateless_caller_issuer_map",
    "stateless_core_issuer_map",
    "stateless_issuer_map",
    "stateless_security_ids",
]
