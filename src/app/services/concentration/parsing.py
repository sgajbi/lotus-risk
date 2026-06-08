from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.concentration import (
    ConcentrationValuationContext,
    StatelessConcentrationInput,
)
from app.services.concentration.datamodels import IssuerIdentity, PositionEntry, IssuerEntry
from app.services.concentration.issuer_mapping import (
    _caller_issuer_map,
    _extract_issuer_map,
    _issuer_key_from_mapping,
    _issuer_key_from_position,
    _merge_issuer_maps,
    _to_weighted_values,
)


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


def _to_exposure_value(
    value: Decimal,
) -> float:  # monetary-float-allow: concentration exposure value.
    return float(value)  # monetary-float-allow: concentration exposure value.


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
            values.append(_to_exposure_value(candidate))
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
                    value=_to_exposure_value(candidate),
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
                    value=_to_exposure_value(candidate),
                )
            )

    return current_rows, proposed_rows


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
        value=_to_exposure_value(candidate),
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


__all__ = [
    "_apply_snapshot_display_names",
    "_as_datetime",
    "_as_int",
    "_as_str",
    "_caller_issuer_map",
    "_extract_issuer_map",
    "_extract_valuation_context",
    "_extract_values_from_snapshot_positions",
    "_extract_values_from_stateless_payload",
    "_extract_values_with_issuer_from_snapshot",
    "_issuer_key_from_mapping",
    "_issuer_key_from_position",
    "_merge_issuer_maps",
    "_to_weighted_values",
    "_to_exposure_value",
]
