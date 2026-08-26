from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

CANONICAL_LIVE_PORTFOLIO_ID = "PB_SG_GLOBAL_BAL_001"
CANONICAL_LIVE_AS_OF_DATE = "2026-03-31"

LIVE_PORTFOLIO_ID_ENV = "LOTUS_RISK_LIVE_PORTFOLIO_ID"
LIVE_AS_OF_DATE_ENV = "LOTUS_RISK_LIVE_AS_OF_DATE"
LIVE_PORTFOLIO_MATRIX_JSON_ENV = "LOTUS_RISK_LIVE_PORTFOLIO_MATRIX_JSON"

SUPPORTED_LIVE_ENDPOINTS = (
    "risk/calculate",
    "drawdown",
    "concentration",
    "rolling-metrics",
    "historical-attribution",
)
HISTORICAL_ATTRIBUTION_ACTIVE_RISK_GROUPINGS = (
    "POSITION",
    "SECTOR",
    "ASSET_CLASS",
    "ISSUER",
)

REQUIRED_PORTFOLIO_ARCHETYPES = (
    "global_balanced",
    "equity_heavy",
    "fixed_income_heavy",
    "cash_heavy",
    "multi_currency",
    "short_history",
    "sparse_benchmark",
    "high_concentration",
)


@dataclass(frozen=True)
class LivePortfolioCase:
    portfolio_id: str
    archetype: str
    label: str
    as_of_date: str = CANONICAL_LIVE_AS_OF_DATE
    supported_endpoints: tuple[str, ...] = SUPPORTED_LIVE_ENDPOINTS
    supportability_note: str = "validated live"


def live_portfolio_id(env: Mapping[str, str] | None = None) -> str:
    values = env or os.environ
    return values.get(LIVE_PORTFOLIO_ID_ENV, CANONICAL_LIVE_PORTFOLIO_ID)


def live_as_of_date(env: Mapping[str, str] | None = None) -> str:
    values = env or os.environ
    return values.get(LIVE_AS_OF_DATE_ENV, CANONICAL_LIVE_AS_OF_DATE)


def default_live_portfolio_case(env: Mapping[str, str] | None = None) -> LivePortfolioCase:
    return LivePortfolioCase(
        portfolio_id=live_portfolio_id(env),
        archetype="global_balanced",
        label="Canonical Singapore global balanced portfolio",
        as_of_date=live_as_of_date(env),
    )


def load_live_portfolio_matrix(
    env: Mapping[str, str] | None = None,
) -> tuple[LivePortfolioCase, ...]:
    values = env or os.environ
    raw_matrix = values.get(LIVE_PORTFOLIO_MATRIX_JSON_ENV)
    if raw_matrix is None or raw_matrix.strip() == "":
        return (default_live_portfolio_case(values),)

    try:
        parsed = json.loads(raw_matrix)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{LIVE_PORTFOLIO_MATRIX_JSON_ENV} must contain valid JSON") from exc

    if not isinstance(parsed, list):
        # The environment value parsed as JSON but violates the configured matrix shape.
        raise ValueError(  # noqa: TRY004
            f"{LIVE_PORTFOLIO_MATRIX_JSON_ENV} must be a JSON array"
        )

    cases = tuple(_case_from_mapping(item) for item in parsed)
    if not cases:
        raise ValueError(f"{LIVE_PORTFOLIO_MATRIX_JSON_ENV} must contain at least one portfolio")
    return cases


def missing_required_archetypes(cases: Sequence[LivePortfolioCase]) -> tuple[str, ...]:
    present = {case.archetype for case in cases}
    return tuple(
        archetype for archetype in REQUIRED_PORTFOLIO_ARCHETYPES if archetype not in present
    )


def _case_from_mapping(value: Any) -> LivePortfolioCase:
    if not isinstance(value, dict):
        # A JSON array entry has the wrong configured value shape, not a Python API argument type.
        raise ValueError("each live portfolio matrix entry must be an object")  # noqa: TRY004

    portfolio_id = _required_string(value, "portfolio_id")
    archetype = _required_string(value, "archetype")
    if archetype not in REQUIRED_PORTFOLIO_ARCHETYPES:
        raise ValueError(f"unsupported live portfolio archetype: {archetype}")

    supported_endpoints = _optional_string_tuple(
        value, "supported_endpoints", SUPPORTED_LIVE_ENDPOINTS
    )
    return LivePortfolioCase(
        portfolio_id=portfolio_id,
        archetype=archetype,
        label=_optional_string(value, "label", portfolio_id),
        as_of_date=_optional_string(value, "as_of_date", CANONICAL_LIVE_AS_OF_DATE),
        supported_endpoints=supported_endpoints,
        supportability_note=_optional_string(
            value,
            "supportability_note",
            "configured live validation case",
        ),
    )


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or item.strip() == "":
        raise ValueError(f"live portfolio matrix entry requires non-empty string field {key!r}")
    return item


def _optional_string(value: dict[str, Any], key: str, default: str) -> str:
    item = value.get(key, default)
    if not isinstance(item, str) or item.strip() == "":
        raise ValueError(f"live portfolio matrix field {key!r} must be a non-empty string")
    return item


def _optional_string_tuple(
    value: dict[str, Any],
    key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    item = value.get(key)
    if item is None:
        return default
    if not isinstance(item, list) or not item:
        raise ValueError(f"live portfolio matrix field {key!r} must be a non-empty string array")
    if not all(isinstance(entry, str) and entry.strip() for entry in item):
        raise ValueError(f"live portfolio matrix field {key!r} must contain only non-empty strings")
    unsupported = sorted(set(item) - set(SUPPORTED_LIVE_ENDPOINTS))
    if unsupported:
        raise ValueError(f"unsupported live validation endpoints: {', '.join(unsupported)}")
    return tuple(item)
