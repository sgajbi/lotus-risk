from fastapi.testclient import TestClient

from app.main import app


def test_concentration_preserves_explicit_zero_projected_book() -> None:
    client = TestClient(app)
    payload = {
        "input_mode": "stateless",
        "enrichment_policy": "use_caller_only",
        "stateless_input": {
            "current_positions": [
                {"security_id": "A", "quantity": 100, "issuer_id": "I1"},
                {"security_id": "B", "quantity": 100, "issuer_id": "I1"},
                {"security_id": "C", "quantity": 200, "issuer_id": "I2"},
            ],
            "projected_positions": [
                {"security_id": "A", "proposed_quantity": 0, "issuer_id": "I1"},
                {"security_id": "B", "proposed_quantity": 0, "issuer_id": "I1"},
                {"security_id": "C", "proposed_quantity": 0, "issuer_id": "I2"},
            ],
            "top_n": 2,
        },
    }

    response = client.post("/analytics/risk/concentration", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["risk_proxy"] == {
        "hhi_current": 3750.0,
        "hhi_proposed": 0.0,
        "hhi_delta": -3750.0,
    }
    assert body["issuer_concentration"]["hhi_proposed"] == 0.0
    assert body["issuer_concentration"]["total_position_count_proposed"] == 0
    assert body["single_position_concentration"]["top_position_proposed"] == {
        "security_id": None,
        "security_name": None,
        "weight": 0.0,
    }


def test_concentration_uses_current_book_when_projection_is_omitted() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "input_mode": "stateless",
            "enrichment_policy": "use_caller_only",
            "stateless_input": {
                "current_positions": [
                    {"security_id": "A", "quantity": 100, "issuer_id": "I1"},
                    {"security_id": "B", "quantity": 100, "issuer_id": "I1"},
                    {"security_id": "C", "quantity": 200, "issuer_id": "I2"},
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_proxy"] == {
        "hhi_current": 3750.0,
        "hhi_proposed": 3750.0,
        "hhi_delta": 0.0,
    }
    assert body["issuer_concentration"]["total_position_count_proposed"] == 3
    assert body["single_position_concentration"]["top_position_proposed"] == {
        "security_id": "C",
        "security_name": None,
        "weight": 0.5,
    }
