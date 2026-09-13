"""Structural validation for the contribution response envelope."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def extract_period_rows(
    response: Mapping[str, Any],
    *,
    dimension_field: str,
    malformed: Callable[[str], Exception],
) -> list[Mapping[str, Any]] | None:
    """Return the requested hierarchy rows; only omitted EXPLICIT is absence."""
    levels = _explicit_levels(response, malformed=malformed)
    if levels is None:
        return None
    for level in levels:
        if _level_name(level, malformed=malformed) == dimension_field:
            return _level_rows(level, dimension_field=dimension_field, malformed=malformed)
    raise malformed(
        f"results_by_period.EXPLICIT.levels missing requested hierarchy {dimension_field!r}"
    )


def _explicit_levels(
    response: Mapping[str, Any],
    *,
    malformed: Callable[[str], Exception],
) -> list[Any] | None:
    if "results_by_period" not in response:
        raise malformed("payload missing results_by_period mapping")
    results = response["results_by_period"]
    if not isinstance(results, Mapping):
        raise malformed("results_by_period is not a mapping")
    if "EXPLICIT" not in results:
        return None
    period = results["EXPLICIT"]
    if not isinstance(period, Mapping):
        raise malformed("results_by_period.EXPLICIT is not a mapping")
    if "levels" not in period or not isinstance(period["levels"], list):
        raise malformed("results_by_period.EXPLICIT.levels is not a list")
    return period["levels"]


def _level_name(level: Any, *, malformed: Callable[[str], Exception]) -> str:
    if not isinstance(level, Mapping):
        raise malformed("results_by_period.EXPLICIT.levels contains a non-mapping level")
    name = level.get("name")
    if not isinstance(name, str):
        raise malformed("results_by_period.EXPLICIT.levels contains a level without a name")
    return name


def _level_rows(
    level: Any,
    *,
    dimension_field: str,
    malformed: Callable[[str], Exception],
) -> list[Mapping[str, Any]]:
    assert isinstance(level, Mapping)
    rows = level.get("rows")
    if not isinstance(rows, list):
        raise malformed(f"hierarchy level {dimension_field!r} rows is not a list")
    if any(not isinstance(row, Mapping) for row in rows):
        raise malformed(f"hierarchy level {dimension_field!r} contains a non-mapping row")
    return rows


__all__ = ["extract_period_rows"]
