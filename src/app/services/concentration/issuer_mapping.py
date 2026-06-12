from __future__ import annotations

from typing import Any

from app.contracts.concentration import (
    EnrichmentPolicy,
    IssuerGroupingLevel,
    IssuerMappingInput,
)
from app.services.concentration.datamodels import IssuerEntry, IssuerIdentity, PositionEntry


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _caller_issuer_map(
    *,
    mappings: list[IssuerMappingInput],
    grouping_level: IssuerGroupingLevel,
) -> dict[str, IssuerIdentity]:
    issuer_by_security: dict[str, IssuerIdentity] = {}
    for mapping in mappings:
        issuer_key = _issuer_key_from_mapping(mapping, grouping_level=grouping_level)
        if issuer_key:
            issuer_by_security[mapping.security_id] = issuer_key
    return issuer_by_security


def _merge_issuer_maps(
    *,
    caller_map: dict[str, IssuerIdentity],
    core_map: dict[str, IssuerIdentity],
    policy: EnrichmentPolicy,
) -> dict[str, IssuerIdentity]:
    if policy == EnrichmentPolicy.USE_CALLER_ONLY:
        return dict(caller_map)
    if policy == EnrichmentPolicy.CORE_ONLY:
        return dict(core_map)
    merged = dict(core_map)
    merged.update(caller_map)
    return merged


def _issuer_key_from_mapping(
    mapping: IssuerMappingInput,
    *,
    grouping_level: IssuerGroupingLevel,
) -> IssuerIdentity | None:
    if grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
        issuer_id = mapping.ultimate_parent_issuer_id or mapping.issuer_id
        issuer_name = mapping.ultimate_parent_issuer_name or mapping.issuer_name
    else:
        issuer_id = mapping.issuer_id
        issuer_name = mapping.issuer_name
    if not issuer_id:
        return None
    return IssuerIdentity(issuer_id=issuer_id, issuer_name=issuer_name)


def _issuer_key_from_position(
    *,
    issuer_id: str | None,
    issuer_name: str | None,
    ultimate_parent_issuer_id: str | None,
    ultimate_parent_issuer_name: str | None,
    grouping_level: IssuerGroupingLevel,
) -> IssuerIdentity | None:
    if grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
        resolved_id = ultimate_parent_issuer_id or issuer_id
        resolved_name = ultimate_parent_issuer_name or issuer_name
    else:
        resolved_id = issuer_id
        resolved_name = issuer_name
    if not resolved_id:
        return None
    return IssuerIdentity(issuer_id=resolved_id, issuer_name=resolved_name)


def _to_weighted_values(
    rows: list[PositionEntry],
    *,
    issuer_by_security: dict[str, IssuerIdentity],
) -> tuple[list[PositionEntry], list[IssuerEntry], int, int]:
    issuer_totals: dict[str, IssuerEntry] = {}
    covered = 0
    total = 0
    for row in rows:
        total += 1
        if row.security_id and row.security_id in issuer_by_security:
            issuer = issuer_by_security[row.security_id]
            existing = issuer_totals.get(issuer.issuer_id)
            if existing is None:
                issuer_totals[issuer.issuer_id] = IssuerEntry(
                    issuer_id=issuer.issuer_id,
                    issuer_name=issuer.issuer_name,
                    value=row.value,
                )
            else:
                existing.value += row.value
            covered += 1
    return rows, list(issuer_totals.values()), covered, total


def _extract_issuer_map(
    sections: dict[str, Any],
    *,
    grouping_level: IssuerGroupingLevel,
) -> tuple[dict[str, IssuerIdentity], str | None]:
    enrichment = sections.get("instrument_enrichment")
    if not isinstance(enrichment, list):
        return {}, "instrument_enrichment missing from lotus-core snapshot"
    issuer_by_security: dict[str, IssuerIdentity] = {}
    for row in enrichment:
        if not isinstance(row, dict):
            continue
        security_id = _as_str(row.get("security_id"))
        if grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT:
            issuer_id = _as_str(row.get("ultimate_parent_issuer_id")) or _as_str(
                row.get("issuer_id")
            )
            issuer_name = _as_str(row.get("ultimate_parent_issuer_name")) or _as_str(
                row.get("issuer_name")
            )
        else:
            issuer_id = _as_str(row.get("issuer_id"))
            issuer_name = _as_str(row.get("issuer_name"))
        if security_id and issuer_id:
            issuer_by_security[security_id] = IssuerIdentity(
                issuer_id=issuer_id,
                issuer_name=issuer_name,
            )
    if not issuer_by_security:
        return {}, "issuer_id missing in lotus-core instrument_enrichment"
    return issuer_by_security, None


__all__ = [
    "_caller_issuer_map",
    "_extract_issuer_map",
    "_issuer_key_from_mapping",
    "_issuer_key_from_position",
    "_merge_issuer_maps",
    "_to_weighted_values",
]
