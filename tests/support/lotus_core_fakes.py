from __future__ import annotations


class SimulationLotusCoreClient:
    def __init__(
        self,
        *,
        session_id: str,
        simulation_version: int,
        include_ultimate_parent_issuer_id: bool = False,
    ) -> None:
        self._session_id = session_id
        self._simulation_version = simulation_version
        self._include_ultimate_parent_issuer_id = include_ultimate_parent_issuer_id

    async def create_simulation_session(
        self,
        *,
        portfolio_id: str,
        ttl_hours: int | None,
        created_by: str | None,
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {
            "session": {
                "session_id": self._session_id,
                "portfolio_id": portfolio_id,
                "status": "ACTIVE",
                "version": 1,
                "created_by": created_by,
                "created_at": "2026-02-27T10:30:00Z",
                "expires_at": "2026-02-28T10:30:00Z",
            }
        }

    async def add_simulation_changes(
        self,
        *,
        session_id: str,
        changes: list[dict[str, object]],
        correlation_id: str | None,
    ) -> dict[str, object]:
        assert session_id == self._session_id
        assert len(changes) == 1
        return {"session_id": session_id, "version": self._simulation_version, "changes": []}

    async def get_core_snapshot(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        if request_payload.get("snapshot_mode") == "BASELINE":
            return {
                "portfolio_id": portfolio_id,
                "as_of_date": "2026-02-27",
                "snapshot_mode": "BASELINE",
                "valuation_context": {
                    "portfolio_currency": "EUR",
                    "reporting_currency": "USD",
                    "position_basis": "market_value_base",
                    "weight_basis": "total_market_value_base",
                },
                "sections": {
                    "positions_baseline": [
                        {"security_id": "SEC_A", "market_value_base": "80"},
                        {"security_id": "SEC_B", "market_value_base": "20"},
                    ]
                },
            }
        return {
            "portfolio_id": portfolio_id,
            "as_of_date": "2026-02-27",
            "snapshot_mode": "SIMULATION",
            "valuation_context": {
                "portfolio_currency": "EUR",
                "reporting_currency": "USD",
                "position_basis": "market_value_base",
                "weight_basis": "total_market_value_base",
            },
            "simulation": {
                "session_id": self._session_id,
                "version": self._simulation_version,
                "baseline_as_of_date": "2026-02-27",
            },
            "sections": {
                "positions_baseline": [
                    {"security_id": "SEC_A", "market_value_base": "60"},
                    {"security_id": "SEC_B", "market_value_base": "40"},
                ],
                "positions_projected": [
                    {"security_id": "SEC_A", "market_value_base": "90"},
                    {"security_id": "SEC_B", "market_value_base": "10"},
                ],
            },
        }

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, object]:
        records: list[dict[str, object]] = []
        for security_id in security_ids:
            record: dict[str, object] = {
                "security_id": security_id,
                "issuer_id": f"ISSUER_{security_id}",
            }
            if self._include_ultimate_parent_issuer_id:
                record["ultimate_parent_issuer_id"] = f"UPI_{security_id}"
            records.append(record)
        return {"records": records}
