from __future__ import annotations

from math import sqrt

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts.risk_options import RiskOptions
from app.main import app


def _annualization_payload(
    *,
    frequency: str = "DAILY",
    annualization_factor: object = ...,
) -> dict[str, object]:
    options: dict[str, object] = {"frequency": frequency}
    if annualization_factor is not ...:
        options["annualization_factor"] = annualization_factor
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "portfolio_open_date": "2026-01-01",
            "periods": [
                {
                    "type": "EXPLICIT",
                    "name": "Annualization",
                    "from_date": "2026-01-02",
                    "to_date": "2026-01-06",
                }
            ],
            "metrics": ["BETA", "TRACKING_ERROR", "INFORMATION_RATIO"],
            "options": options,
            "returns": [
                {"date": "2026-01-02", "value": -1.0},
                {"date": "2026-01-05", "value": 1.0},
                {"date": "2026-01-06", "value": 3.0},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": -1.0},
                {"date": "2026-01-05", "value": 0.0},
                {"date": "2026-01-06", "value": 1.0},
            ],
        },
    }


@pytest.mark.parametrize(
    ("frequency", "expected_factor"),
    [("DAILY", 252), ("WEEKLY", 52), ("MONTHLY", 12)],
)
@pytest.mark.parametrize("annualization_factor", [..., None])
def test_risk_calculate_uses_frequency_default_only_when_annualization_is_missing_or_null(
    frequency: str,
    expected_factor: int,
    annualization_factor: object,
) -> None:
    response = TestClient(app).post(
        "/analytics/risk/calculate",
        json=_annualization_payload(
            frequency=frequency,
            annualization_factor=annualization_factor,
        ),
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["annualization_factor"] == expected_factor


@pytest.mark.parametrize("annualization_factor", [-1, 1.5, "NaN"])
def test_risk_calculate_refuses_invalid_annualization_before_metric_calculation(
    annualization_factor: float | str,
) -> None:
    response = TestClient(app).post(
        "/analytics/risk/calculate",
        json=_annualization_payload(annualization_factor=annualization_factor),
        headers={"X-Correlation-Id": "annualization-invalid"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert error["correlation_id"] == "annualization-invalid"
    assert any(
        detail["loc"]
        == [
            "body",
            "stateless_input",
            "options",
            "annualization_factor",
        ]
        for detail in error["details"]
    )


@pytest.mark.parametrize("annualization_factor", [0, -1, 1.5, "NaN"])
def test_shared_risk_options_contract_refuses_invalid_annualization_for_all_modes(
    annualization_factor: float | str,
) -> None:
    with pytest.raises(ValidationError):
        RiskOptions.model_validate({"annualization_factor": annualization_factor})

    assert RiskOptions.model_validate({}).annualization_factor is None
    assert RiskOptions.model_validate({"annualization_factor": 12}).annualization_factor == 12


def test_risk_calculate_applies_positive_annualization_override_with_independent_expectations() -> (
    None
):
    response = TestClient(app).post(
        "/analytics/risk/calculate",
        json=_annualization_payload(annualization_factor=12),
    )

    assert response.status_code == 200
    body = response.json()
    metrics = body["results"]["Annualization"]["metrics"]
    assert body["metadata"]["annualization_factor"] == 12
    assert metrics["BETA"]["value"] == pytest.approx(2.0)
    assert metrics["TRACKING_ERROR"]["value"] == pytest.approx(sqrt(12))
    assert metrics["INFORMATION_RATIO"]["value"] == pytest.approx(sqrt(12))
