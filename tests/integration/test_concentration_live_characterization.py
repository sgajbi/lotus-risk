from __future__ import annotations

import os
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import pytest


def _live_enabled() -> bool:
    return os.getenv("LOTUS_RISK_RUN_LIVE_CONCENTRATION") == "1"


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="set LOTUS_RISK_RUN_LIVE_CONCENTRATION=1 to run live concentration reconciliation",
)


RISK_BASE_URL = os.getenv("LOTUS_RISK_BASE_URL", "http://localhost:8130")
CORE_BASE_URL = os.getenv(
    "LOTUS_CORE_BASE_URL",
    os.getenv("LOTUS_CORE_QUERY_BASE_URL", "http://localhost:8202"),
)
PORTFOLIO_ID = os.getenv("LOTUS_RISK_LIVE_PORTFOLIO_ID", "PB_SG_GLOBAL_BAL_001")
AS_OF_DATE = os.getenv("LOTUS_RISK_LIVE_AS_OF_DATE", "2026-03-31")


def _round(value: float) -> float:
    return round(value, 6)


def _position_value(position: dict[str, Any]) -> float:
    for key in ("market_value_base", "quantity"):
        value = position.get(key)
        if value is None:
            continue
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        if decimal_value > 0:
            return float(decimal_value)
    return 0.0


def _hhi(values: Sequence[float]) -> float:
    denominator = sum(abs(value) for value in values)
    if denominator <= 0:
        return 0.0
    return _round(sum((abs(value) / denominator) ** 2 for value in values) * 10000.0)


def _top_weight(values: Sequence[float]) -> float:
    denominator = sum(abs(value) for value in values)
    if denominator <= 0:
        return 0.0
    return _round(max(abs(value) / denominator for value in values))


def _top_n_weight(values: Sequence[float], *, top_n: int) -> float:
    denominator = sum(abs(value) for value in values)
    if denominator <= 0:
        return 0.0
    weights = sorted((abs(value) / denominator for value in values), reverse=True)
    return _round(sum(weights[:top_n]))


def _instrument_name_by_security(enrichment: Sequence[dict[str, Any]]) -> dict[str, str]:
    return {
        row["security_id"]: row["instrument_name"]
        for row in enrichment
        if isinstance(row, dict)
        and isinstance(row.get("security_id"), str)
        and isinstance(row.get("instrument_name"), str)
    }


def _top_position(positions: Sequence[dict[str, Any]]) -> tuple[str, float]:
    usable = [position for position in positions if _position_value(position) > 0]
    assert usable, "expected at least one usable position in live snapshot"
    denominator = sum(_position_value(position) for position in usable)
    top = max(
        usable,
        key=lambda position: (_position_value(position), position.get("security_id") or ""),
    )
    security_id = top.get("security_id")
    assert isinstance(security_id, str), "expected top live position to carry security_id"
    return security_id, _round(_position_value(top) / denominator)


def _top_issuer(
    positions: Sequence[dict[str, Any]],
    enrichment: Sequence[dict[str, Any]],
) -> tuple[str | None, float]:
    issuer_by_security = {
        row.get("security_id"): row.get("ultimate_parent_issuer_id") or row.get("issuer_id")
        for row in enrichment
        if isinstance(row, dict) and row.get("security_id")
    }
    issuer_totals: dict[str, float] = {}
    for position in positions:
        security_id = position.get("security_id")
        issuer_id = issuer_by_security.get(security_id)
        if not issuer_id:
            continue
        issuer_totals[issuer_id] = issuer_totals.get(issuer_id, 0.0) + _position_value(position)
    assert issuer_totals, "expected live snapshot to contain issuer-enriched positions"
    denominator = sum(issuer_totals.values())
    top_issuer_id, top_value = max(issuer_totals.items(), key=lambda item: (item[1], item[0]))
    return top_issuer_id, _round(top_value / denominator)


def _issuer_values(
    positions: Sequence[dict[str, Any]],
    enrichment: Sequence[dict[str, Any]],
) -> tuple[list[float], int, int]:
    issuer_by_security = {
        row.get("security_id"): row.get("ultimate_parent_issuer_id") or row.get("issuer_id")
        for row in enrichment
        if isinstance(row, dict) and row.get("security_id")
    }
    issuer_totals: dict[str, float] = {}
    covered = 0
    total = 0
    for position in positions:
        value = _position_value(position)
        if value <= 0:
            continue
        total += 1
        issuer_id = issuer_by_security.get(position.get("security_id"))
        if not issuer_id:
            continue
        issuer_totals[issuer_id] = issuer_totals.get(issuer_id, 0.0) + value
        covered += 1
    return list(issuer_totals.values()), covered, total


def test_live_stateful_concentration_reconciles_top_drivers() -> None:
    top_n = 10
    snapshot_payload = {
        "as_of_date": AS_OF_DATE,
        "snapshot_mode": "BASELINE",
        "sections": ["positions_baseline", "portfolio_totals", "instrument_enrichment"],
        "options": {
            "include_zero_quantity_positions": False,
            "include_cash_positions": True,
            "position_basis": "market_value_base",
            "weight_basis": "total_market_value_base",
        },
    }
    risk_payload = {
        "input_mode": "stateful",
        "stateful_input": {
            "portfolio_id": PORTFOLIO_ID,
            "as_of_date": AS_OF_DATE,
            "top_n": top_n,
            "include_cash_positions": True,
            "include_zero_quantity_positions": False,
        },
    }

    with httpx.Client(timeout=30.0) as client:
        snapshot_response = client.post(
            f"{CORE_BASE_URL}/integration/portfolios/{PORTFOLIO_ID}/core-snapshot",
            json=snapshot_payload,
        )
        snapshot_response.raise_for_status()
        concentration_response = client.post(
            f"{RISK_BASE_URL}/analytics/risk/concentration",
            json=risk_payload,
        )
        concentration_response.raise_for_status()

    snapshot_body = snapshot_response.json()
    risk_body = concentration_response.json()
    sections = snapshot_body["sections"]
    positions = sections["positions_baseline"]
    enrichment = sections["instrument_enrichment"]

    values = [_position_value(position) for position in positions if _position_value(position) > 0]
    issuer_values, issuer_covered_count, issuer_total_count = _issuer_values(positions, enrichment)
    security_names = _instrument_name_by_security(enrichment)
    expected_top_security_id, expected_top_position_weight = _top_position(positions)
    expected_top_issuer_id, expected_top_issuer_weight = _top_issuer(positions, enrichment)

    assert risk_body["source_service"] == "lotus-risk"
    assert risk_body["input_mode"] == "stateful"
    assert risk_body["metadata"] == {
        "as_of_date": AS_OF_DATE,
        "portfolio_id": PORTFOLIO_ID,
        "simulation_session_id": None,
        "simulation_session_version": None,
        "session_expires_at": None,
        "issuer_grouping_level": "ultimate_parent",
        "enrichment_policy": "merge_caller_then_core",
        "include_cash_positions": True,
        "include_zero_quantity_positions": False,
    }
    assert risk_body["valuation_context"] == {
        "portfolio_currency": "USD",
        "reporting_currency": "USD",
        "position_basis": "market_value_base",
        "weight_basis": "total_market_value_base",
    }
    assert risk_body["risk_proxy"] == {
        "hhi_current": _hhi(values),
        "hhi_proposed": _hhi(values),
        "hhi_delta": 0.0,
    }
    assert risk_body["single_position_concentration"]["top_position_weight_current"] == (
        _top_weight(values)
    )
    assert risk_body["single_position_concentration"]["top_position_weight_proposed"] == (
        _top_weight(values)
    )
    assert risk_body["single_position_concentration"]["top_position_weight_delta"] == 0.0
    assert risk_body["single_position_concentration"]["top_n_cumulative_weight_current"] == (
        _top_n_weight(values, top_n=top_n)
    )
    assert risk_body["single_position_concentration"]["top_n_cumulative_weight_proposed"] == (
        _top_n_weight(values, top_n=top_n)
    )
    assert risk_body["single_position_concentration"]["top_n_cumulative_weight_delta"] == 0.0
    assert risk_body["single_position_concentration"]["top_n"] == top_n
    assert risk_body["single_position_concentration"]["top_position_current"]["security_id"] == (
        expected_top_security_id
    )
    assert (
        risk_body["single_position_concentration"]["top_position_current"]["security_name"]
        == (security_names[expected_top_security_id])
    )
    assert risk_body["single_position_concentration"]["top_position_current"]["weight"] == (
        expected_top_position_weight
    )
    assert risk_body["issuer_concentration"]["hhi_current"] == _hhi(issuer_values)
    assert risk_body["issuer_concentration"]["hhi_proposed"] == _hhi(issuer_values)
    assert risk_body["issuer_concentration"]["hhi_delta"] == 0.0
    assert risk_body["issuer_concentration"]["top_issuer_weight_current"] == _top_weight(
        issuer_values
    )
    assert risk_body["issuer_concentration"]["top_issuer_weight_proposed"] == _top_weight(
        issuer_values
    )
    assert risk_body["issuer_concentration"]["top_issuer_weight_delta"] == 0.0
    assert risk_body["issuer_concentration"]["coverage_status"] == "complete"
    assert risk_body["issuer_concentration"]["covered_position_count_current"] == (
        issuer_covered_count
    )
    assert risk_body["issuer_concentration"]["covered_position_count_proposed"] == (
        issuer_covered_count
    )
    assert risk_body["issuer_concentration"]["total_position_count_current"] == issuer_total_count
    assert risk_body["issuer_concentration"]["total_position_count_proposed"] == issuer_total_count
    assert risk_body["issuer_concentration"]["uncovered_position_count_current"] == 0
    assert risk_body["issuer_concentration"]["uncovered_position_count_proposed"] == 0
    assert risk_body["issuer_concentration"]["coverage_ratio_current"] == 1.0
    assert risk_body["issuer_concentration"]["coverage_ratio_proposed"] == 1.0
    assert risk_body["issuer_concentration"]["note"] is None
    assert risk_body["issuer_concentration"]["top_issuer_current"]["issuer_id"] == (
        expected_top_issuer_id
    )
    assert risk_body["issuer_concentration"]["top_issuer_current"]["weight"] == (
        expected_top_issuer_weight
    )
