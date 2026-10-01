from typing import Any, Protocol, cast

from fastapi.testclient import TestClient

from app.main import app


class _Response(Protocol):
    status_code: int

    def json(self) -> Any: ...


def _post_concentration(stateless_input: dict[str, object]) -> _Response:
    return cast(
        _Response,
        TestClient(app).post(
            "/analytics/risk/concentration",
            json={
                "input_mode": "stateless",
                "enrichment_policy": "use_caller_only",
                "stateless_input": stateless_input,
            },
        ),
    )


def test_concentration_market_value_control_declares_market_value_basis() -> None:
    response = _post_concentration(
        {
            "current_positions": [
                {
                    "security_id": "A",
                    "quantity": 100,
                    "market_value_base": 10_000,
                    "issuer_id": "I1",
                },
                {
                    "security_id": "B",
                    "quantity": 100,
                    "market_value_base": 10_000,
                    "issuer_id": "I2",
                },
            ],
        }
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_proxy"] == {
        "hhi_current": 5000.0,
        "hhi_proposed": 5000.0,
        "hhi_delta": 0.0,
    }
    assert body["valuation_context"] == {
        "portfolio_currency": None,
        "reporting_currency": None,
        "position_basis": "market_value_base",
        "weight_basis": "total_market_value_base",
    }


def test_concentration_zero_market_value_never_falls_back_to_quantity() -> None:
    response = _post_concentration(
        {
            "current_positions": [
                {
                    "security_id": "A",
                    "quantity": 100,
                    "market_value_base": 10_000,
                    "issuer_id": "I1",
                },
                {"security_id": "B", "quantity": 100, "market_value_base": 0, "issuer_id": "I2"},
            ],
            "top_n": 2,
        }
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_proxy"] == {
        "hhi_current": 10000.0,
        "hhi_proposed": 10000.0,
        "hhi_delta": 0.0,
    }
    assert body["single_position_concentration"]["top_position_current"] == {
        "security_id": "A",
        "security_name": None,
        "weight": 1.0,
    }
    assert body["issuer_concentration"]["total_position_count_current"] == 1
    assert body["issuer_concentration"]["coverage_status"] == "complete"


def test_concentration_refuses_partial_market_value_book() -> None:
    response = _post_concentration(
        {
            "current_positions": [
                {"security_id": "A", "quantity": 100, "market_value_base": 10_000},
                {"security_id": "B", "quantity": 100},
            ],
        }
    )

    assert response.status_code == 422
    assert "cannot mix market-value and quantity exposure bases" in str(response.json())


def test_concentration_refuses_missing_exposure_for_quantity_proxy_book() -> None:
    response = _post_concentration(
        {
            "current_positions": [
                {"security_id": "A", "quantity": 100},
                {"security_id": "B"},
            ],
        }
    )

    assert response.status_code == 422
    assert "require every row to provide market value or quantity" in str(response.json())


def test_concentration_quantity_proxy_is_explicit_and_cannot_mix_with_projected_market_values() -> (
    None
):
    quantity_proxy_response = _post_concentration(
        {
            "current_positions": [
                {"security_id": "A", "quantity": 100, "issuer_id": "I1"},
                {"security_id": "B", "quantity": 100, "issuer_id": "I2"},
            ],
            "projected_positions": [
                {"security_id": "A", "proposed_quantity": 100, "issuer_id": "I1"},
                {"security_id": "B", "proposed_quantity": 100, "issuer_id": "I2"},
            ],
        }
    )

    assert quantity_proxy_response.status_code == 200
    assert quantity_proxy_response.json()["valuation_context"] == {
        "portfolio_currency": None,
        "reporting_currency": None,
        "position_basis": "quantity_proxy",
        "weight_basis": "total_quantity_proxy",
    }

    mismatched_response = _post_concentration(
        {
            "current_positions": [
                {"security_id": "A", "quantity": 100},
                {"security_id": "B", "quantity": 100},
            ],
            "projected_positions": [
                {"security_id": "A", "projected_market_value_base": 10_000},
                {"security_id": "B", "projected_market_value_base": 10_000},
            ],
        }
    )

    assert mismatched_response.status_code == 422
    assert "current and projected positions must use the same exposure basis" in str(
        mismatched_response.json()
    )
