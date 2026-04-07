from __future__ import annotations

import os
from collections.abc import Sequence
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
CORE_BASE_URL = os.getenv("LOTUS_CORE_QUERY_BASE_URL", "http://localhost:8202")
PORTFOLIO_ID = os.getenv("LOTUS_RISK_LIVE_PORTFOLIO_ID", "PB_SG_GLOBAL_BAL_001")
AS_OF_DATE = os.getenv("LOTUS_RISK_LIVE_AS_OF_DATE", "2026-03-31")


def _position_value(position: dict[str, Any]) -> float:
    market_value = position.get("market_value_base")
    if market_value is not None:
        return abs(float(market_value))
    quantity = position.get("quantity")
    if quantity is not None:
        return abs(float(quantity))
    return 0.0


def _top_position(positions: Sequence[dict[str, Any]]) -> tuple[str | None, float]:
    usable = [position for position in positions if _position_value(position) > 0]
    assert usable, "expected at least one usable position in live snapshot"
    denominator = sum(_position_value(position) for position in usable)
    top = max(
        usable,
        key=lambda position: (_position_value(position), position.get("security_id") or ""),
    )
    return top.get("security_id"), round(_position_value(top) / denominator, 6)


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
    return top_issuer_id, round(top_value / denominator, 6)


def test_live_stateful_concentration_reconciles_top_drivers() -> None:
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
            "top_n": 10,
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

    expected_top_security_id, expected_top_position_weight = _top_position(positions)
    expected_top_issuer_id, expected_top_issuer_weight = _top_issuer(positions, enrichment)

    assert risk_body["single_position_concentration"]["top_position_current"]["security_id"] == (
        expected_top_security_id
    )
    assert risk_body["single_position_concentration"]["top_position_current"]["weight"] == (
        expected_top_position_weight
    )
    assert risk_body["issuer_concentration"]["top_issuer_current"]["issuer_id"] == (
        expected_top_issuer_id
    )
    assert risk_body["issuer_concentration"]["top_issuer_current"]["weight"] == (
        expected_top_issuer_weight
    )
