from __future__ import annotations

from typing import Any

from app.services.concentration.datamodels import IssuerIdentity


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def apply_snapshot_display_names(
    sections: dict[str, Any],
    issuer_by_security: dict[str, IssuerIdentity],
) -> None:
    enrichment = sections.get("instrument_enrichment")
    if not isinstance(enrichment, list):
        return
    security_names = security_names_from_enrichment(enrichment)
    apply_display_names_to_snapshot_positions(sections, security_names)


def security_names_from_enrichment(enrichment: list[Any]) -> dict[str, str]:
    security_names: dict[str, str] = {}
    for row in enrichment:
        if not isinstance(row, dict):
            continue
        security_id = _as_str(row.get("security_id"))
        instrument_name = _as_str(row.get("instrument_name"))
        if security_id and instrument_name:
            security_names[security_id] = instrument_name
    return security_names


def apply_display_names_to_snapshot_positions(
    sections: dict[str, Any],
    security_names: dict[str, str],
) -> None:
    for section_name in ("positions_baseline", "positions_projected", "positions_delta"):
        positions = sections.get(section_name)
        if not isinstance(positions, list):
            continue
        apply_display_names_to_rows(positions, security_names)


def apply_display_names_to_rows(
    positions: list[Any],
    security_names: dict[str, str],
) -> None:
    for row in positions:
        if not isinstance(row, dict):
            continue
        security_id = _as_str(row.get("security_id"))
        if security_id and security_id in security_names and "instrument_name" not in row:
            row["instrument_name"] = security_names[security_id]


__all__ = [
    "apply_display_names_to_rows",
    "apply_display_names_to_snapshot_positions",
    "apply_snapshot_display_names",
    "security_names_from_enrichment",
]
