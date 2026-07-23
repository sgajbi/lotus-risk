from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from app.evidence.idea_opportunity_runtime import (
    build_idea_opportunity_runtime_evidence,
    idea_opportunity_runtime_evidence_is_valid,
)
from app.main import app


def test_idea_opportunity_runtime_evidence_executes_live_api_routes() -> None:
    client = TestClient(app)

    def execute(route: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        response = client.post(route, json=payload)
        return response.status_code, response.json()

    evidence = build_idea_opportunity_runtime_evidence(
        execute=execute,
        generated_at_utc=datetime(2026, 7, 23, 6, 30, tzinfo=UTC),
    )

    assert idea_opportunity_runtime_evidence_is_valid(evidence) is True
    assert [execution["receipt"]["route"] for execution in evidence["executions"]] == [
        "/analytics/risk/concentration",
        "/analytics/risk/calculate",
        "/analytics/risk/drawdown",
    ]
    assert all(execution["receipt"]["summary"] for execution in evidence["executions"])
