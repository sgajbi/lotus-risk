"""Public HTTP observation journey through supported and unmatched routes."""

from fastapi.testclient import TestClient

from app.main import app


def test_e2e_http_metrics_distinguish_supported_routes_from_unmatched_input() -> None:
    client = TestClient(app)

    assert client.get("/version").status_code == 200
    assert client.head("/docs").status_code == 200
    assert client.patch("/attacker/controlled").status_code == 404
    metrics = client.get("/metrics").text

    assert 'handler="/version",method="GET",status="2xx"' in metrics
    assert 'handler="/docs",method="HEAD",status="2xx"' in metrics
    assert 'handler="unmatched",method="OTHER",status="4xx"' in metrics
    assert "/attacker/controlled" not in metrics
    assert 'method="PATCH"' not in metrics
