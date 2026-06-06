from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.concentration import (
    ConcentrationValuationContext,
    EnrichmentPolicy,
    IssuerGroupingLevel,
    IssuerMappingInput,
    StatelessConcentrationInput,
)
from app.services.concentration.datamodels import IssuerIdentity, PositionEntry, IssuerEntry


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _as_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if decimal_value <= 0:
        return None
    return decimal_value


def _extract_values_from_snapshot_positions(positions: list[dict[str, Any]] | None) -> list[float]:
    if not positions:
        return []
    values: list[float] = []
    for position in positions:
        if not isinstance(position, dict):
            continue
        candidate = _to_decimal(position.get("market_value_base"))
        if candidate is None:
            candidate = _to_decimal(position.get("quantity"))
        if candidate is not None:
            values.append(float(candidate))
    return values


def _extract_values_from_stateless_payload(
    payload: StatelessConcentrationInput,
) -> tuple[list[PositionEntry], list[PositionEntry]]:
    current_rows: list[PositionEntry] = []
    for position in payload.current_positions:
        candidate = _to_decimal(position.market_value_base)
        if candidate is None:
            candidate = _to_decimal(position.quantity)
        if candidate is not None:
            current_rows.append(
                PositionEntry(
                    security_id=position.security_id,
                    security_name=position.security_name,
                    value=float(candidate),
                )
            )

    proposed_rows: list[PositionEntry] = []
    for projected_position in payload.projected_positions:
        candidate = _to_decimal(projected_position.projected_market_value_base)
        if candidate is None:
            candidate = _to_decimal(projected_position.proposed_quantity)
        if candidate is not None:
            proposed_rows.append(
                PositionEntry(
                    security_id=projected_position.security_id,
                    security_name=projected_position.security_name,
                    value=float(candidate),
                )
            )

    return current_rows, proposed_rows


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


def _apply_snapshot_display_names(
    sections: dict[str, Any],
    issuer_by_security: dict[str, IssuerIdentity],
) -> None:
    enrichment = sections.get("instrument_enrichment")
    if not isinstance(enrichment, list):
        return
    security_names = _security_names_from_enrichment(enrichment)
    _apply_display_names_to_snapshot_positions(sections, security_names)


def _security_names_from_enrichment(enrichment: list[Any]) -> dict[str, str]:
    security_names: dict[str, str] = {}
    for row in enrichment:
        if not isinstance(row, dict):
            continue
        security_id = _as_str(row.get("security_id"))
        instrument_name = _as_str(row.get("instrument_name"))
        if security_id and instrument_name:
            security_names[security_id] = instrument_name
    return security_names


def _apply_display_names_to_snapshot_positions(
    sections: dict[str, Any],
    security_names: dict[str, str],
) -> None:
    for section_name in ("positions_baseline", "positions_projected", "positions_delta"):
        positions = sections.get(section_name)
        if not isinstance(positions, list):
            continue
        _apply_display_names_to_rows(positions, security_names)


def _apply_display_names_to_rows(
    positions: list[Any],
    security_names: dict[str, str],
) -> None:
    for row in positions:
        if not isinstance(row, dict):
            continue
        security_id = _as_str(row.get("security_id"))
        if security_id and security_id in security_names and "instrument_name" not in row:
            row["instrument_name"] = security_names[security_id]


def _snapshot_position_entry(position: dict[str, Any]) -> PositionEntry | None:
    candidate = _to_decimal(position.get("market_value_base"))
    if candidate is None:
        candidate = _to_decimal(position.get("quantity"))
    if candidate is None:
        return None
    return PositionEntry(
        security_id=_as_str(position.get("security_id")),
        security_name=_as_str(position.get("instrument_name")),
        value=float(candidate),  # monetary-float-allow: concentration exposure value.
    )


def _extract_values_with_issuer_from_snapshot(
    positions: list[dict[str, Any]] | None,
    issuer_by_security: dict[str, IssuerIdentity],
) -> tuple[list[PositionEntry], list[IssuerEntry], int, int]:
    if not positions:
        return [], [], 0, 0
    position_entries: list[PositionEntry] = []
    issuer_totals: dict[str, IssuerEntry] = {}
    covered = 0
    total = 0
    for position in positions:
        if not isinstance(position, dict):
            continue
        position_entry = _snapshot_position_entry(position)
        if position_entry is None:
            continue
        position_entries.append(position_entry)
        total += 1
        security_id = position_entry.security_id
        if security_id and security_id in issuer_by_security:
            issuer = issuer_by_security[security_id]
            existing = issuer_totals.get(issuer.issuer_id)
            if existing is None:
                issuer_totals[issuer.issuer_id] = IssuerEntry(
                    issuer_id=issuer.issuer_id,
                    issuer_name=issuer.issuer_name,
                    value=position_entry.value,
                )
            else:
                existing.value += position_entry.value
            covered += 1
    return position_entries, list(issuer_totals.values()), covered, total


def _extract_valuation_context(raw_context: Any) -> ConcentrationValuationContext | None:
    if not isinstance(raw_context, dict):
        return None
    return ConcentrationValuationContext(
        portfolio_currency=_as_str(raw_context.get("portfolio_currency")),
        reporting_currency=_as_str(raw_context.get("reporting_currency")),
        position_basis=_as_str(raw_context.get("position_basis")),
        weight_basis=_as_str(raw_context.get("weight_basis")),
    )
