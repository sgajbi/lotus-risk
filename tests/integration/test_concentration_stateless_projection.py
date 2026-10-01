import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize(
    ("grouping_level", "current_issuer", "projected_issuer"),
    [
        ("legal_issuer", "I2", "I1"),
        ("ultimate_parent", "P2", "P1"),
    ],
)
def test_projected_issuer_metadata_cannot_rewrite_baseline_concentration(
    grouping_level: str,
    current_issuer: str,
    projected_issuer: str,
) -> None:
    """The independent current oracle is two 50% issuer buckets: HHI 5,000."""
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        headers={"X-Tenant-Id": "synthetic-issuer-review"},
        json={
            "input_mode": "stateless",
            "enrichment_policy": "use_caller_only",
            "issuer_grouping_level": grouping_level,
            "stateless_input": {
                "current_positions": [
                    {
                        "security_id": "A",
                        "market_value_base": 100,
                        "issuer_id": "I1",
                        "ultimate_parent_issuer_id": "P1",
                    },
                    {
                        "security_id": "B",
                        "market_value_base": 100,
                        "issuer_id": current_issuer,
                        "ultimate_parent_issuer_id": current_issuer,
                    },
                ],
                "projected_positions": [
                    {
                        "security_id": "A",
                        "projected_market_value_base": 100,
                        "issuer_id": "I1",
                        "ultimate_parent_issuer_id": "P1",
                    },
                    {
                        "security_id": "B",
                        "projected_market_value_base": 100,
                        "issuer_id": projected_issuer,
                        "ultimate_parent_issuer_id": projected_issuer,
                    },
                ],
            },
        },
    )

    assert response.status_code == 200
    issuer = response.json()["issuer_concentration"]
    assert issuer["hhi_current"] == 5000.0
    assert issuer["top_issuer_current"]["weight"] == 0.5
    assert issuer["hhi_proposed"] == 10000.0
    assert issuer["hhi_delta"] == 5000.0


def test_projected_row_without_issuer_metadata_keeps_current_issuer_identity() -> None:
    client = TestClient(app)
    response = client.post(
        "/analytics/risk/concentration",
        json={
            "input_mode": "stateless",
            "enrichment_policy": "use_caller_only",
            "issuer_grouping_level": "legal_issuer",
            "stateless_input": {
                "current_positions": [
                    {"security_id": "A", "market_value_base": 100, "issuer_id": "I1"},
                    {"security_id": "B", "market_value_base": 100, "issuer_id": "I2"},
                ],
                "projected_positions": [
                    {"security_id": "A", "projected_market_value_base": 100},
                    {"security_id": "B", "projected_market_value_base": 100},
                ],
            },
        },
    )

    assert response.status_code == 200
    issuer = response.json()["issuer_concentration"]
    assert issuer["hhi_current"] == 5000.0
    assert issuer["hhi_proposed"] == 5000.0
    assert issuer["hhi_delta"] == 0.0


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
