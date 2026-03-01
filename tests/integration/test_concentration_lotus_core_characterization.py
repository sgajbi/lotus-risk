from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


class _RecordingLotusCoreClient:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.change_calls: list[dict[str, Any]] = []
        self.snapshot_calls: list[dict[str, Any]] = []

    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        self.create_calls.append(
            {
                "portfolio_id": portfolio_id,
                "ttl_hours": ttl_hours,
                "created_by": created_by,
                "correlation_id": correlation_id,
            }
        )
        return {"session": {"session_id": "SIM_9000", "version": 1}}

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, Any]],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        self.change_calls.append(
            {
                "session_id": session_id,
                "changes": changes,
                "correlation_id": correlation_id,
            }
        )
        return {"session_id": session_id, "version": 7}

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        self.snapshot_calls.append(
            {
                "portfolio_id": portfolio_id,
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        if request_payload.get("snapshot_mode") == "BASELINE":
            return {
                "valuation_context": {"portfolio_currency": "EUR", "reporting_currency": "USD"},
                "sections": {
                    "positions_baseline": [
                        {
                            "security_id": "SEC_A",
                            "market_value_base": "60",
                        },
                        {
                            "security_id": "SEC_B",
                            "market_value_base": "40",
                        },
                    ],
                    "instrument_enrichment": [
                        {"security_id": "SEC_A", "issuer_id": "ISSUER_A"},
                        {"security_id": "SEC_B", "issuer_id": "ISSUER_B"},
                    ],
                },
            }
        return {
            "simulation": {"session_id": "SIM_9000", "version": 7},
            "sections": {
                "positions_baseline": [
                    {"security_id": "SEC_A", "market_value_base": "60"},
                    {"security_id": "SEC_B", "market_value_base": "40"},
                ],
                "positions_projected": [
                    {"security_id": "SEC_A", "market_value_base": "70"},
                    {"security_id": "SEC_B", "market_value_base": "30"},
                ],
                "instrument_enrichment": [
                    {"security_id": "SEC_A", "issuer_id": "ISSUER_A"},
                    {"security_id": "SEC_B", "issuer_id": "ISSUER_B"},
                ],
            },
        }

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]:
        return {
            "records": [
                {"security_id": security_id, "issuer_id": f"ISSUER_{security_id}"}
                for security_id in security_ids
            ]
        }


def test_stateful_api_characterizes_lotus_core_snapshot_payload_contract() -> None:
    core_client = _RecordingLotusCoreClient()
    app.state.lotus_core_client = core_client
    client = TestClient(app)

    response = client.post(
        "/analytics/risk/concentration",
        headers={"X-Correlation-Id": "corr-stateful"},
        json={
            "input_mode": "stateful",
            "issuer_grouping_level": "legal_issuer",
            "enrichment_policy": "core_only",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "reporting_currency": "USD",
                "include_cash_positions": False,
                "include_zero_quantity_positions": True,
                "top_n": 5,
            },
        },
    )

    assert response.status_code == 200
    assert len(core_client.snapshot_calls) == 1
    snapshot_call = core_client.snapshot_calls[0]
    assert snapshot_call["portfolio_id"] == "DEMO_DPM_EUR_001"
    assert snapshot_call["correlation_id"] == "corr-stateful"
    payload = snapshot_call["request_payload"]
    assert payload["snapshot_mode"] == "BASELINE"
    assert payload["sections"] == [
        "positions_baseline",
        "portfolio_totals",
        "instrument_enrichment",
    ]
    assert payload["reporting_currency"] == "USD"
    assert payload["options"] == {
        "include_zero_quantity_positions": True,
        "include_cash_positions": False,
        "position_basis": "market_value_base",
        "weight_basis": "total_market_value_base",
    }


def test_simulation_api_characterizes_session_creation_and_snapshot_contract() -> None:
    core_client = _RecordingLotusCoreClient()
    app.state.lotus_core_client = core_client
    client = TestClient(app)

    response = client.post(
        "/analytics/risk/concentration",
        headers={"X-Correlation-Id": "corr-sim", "X-Actor-Id": "risk-tester"},
        json={
            "input_mode": "simulation",
            "simulation_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "session_ttl_hours": 24,
                "simulation_changes": [
                    {"security_id": "SEC_A", "transaction_type": "BUY", "quantity": 10}
                ],
            },
        },
    )

    assert response.status_code == 200
    assert len(core_client.create_calls) == 1
    assert core_client.create_calls[0] == {
        "portfolio_id": "DEMO_DPM_EUR_001",
        "ttl_hours": 24,
        "created_by": "risk-tester",
        "correlation_id": "corr-sim",
    }
    assert len(core_client.change_calls) == 1
    assert core_client.change_calls[0]["session_id"] == "SIM_9000"
    assert core_client.change_calls[0]["correlation_id"] == "corr-sim"
    snapshot_payload = core_client.snapshot_calls[0]["request_payload"]
    assert snapshot_payload["snapshot_mode"] == "SIMULATION"
    assert snapshot_payload["simulation"] == {"session_id": "SIM_9000", "expected_version": 7}
    assert snapshot_payload["sections"] == [
        "positions_baseline",
        "positions_projected",
        "positions_delta",
        "portfolio_totals",
        "instrument_enrichment",
    ]
