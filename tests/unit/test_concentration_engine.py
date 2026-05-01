from app.contracts.concentration import ConcentrationRequest
from app.observability_contracts import RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS
from app.services.concentration_engine import _compute_hhi, calculate_concentration
import pytest
from pydantic import ValidationError


def test_compute_hhi_handles_empty_and_zero_total() -> None:
    assert _compute_hhi([]) == 0.0
    assert _compute_hhi([0.0, 0.0]) == 0.0


def test_compute_hhi_equal_weights() -> None:
    assert _compute_hhi([10.0, 10.0]) == 5000.0


@pytest.mark.asyncio
async def test_calculate_concentration_stateless_uses_projected_values_when_provided() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateless",
            "stateless_input": {
                "current_positions": [
                    {
                        "security_id": "A",
                        "security_name": "Alpha Holdings",
                        "quantity": 10,
                        "issuer_id": "ISSUER_ALPHA",
                    },
                    {
                        "security_id": "B",
                        "security_name": "Beta Bonds",
                        "quantity": 10,
                        "issuer_id": "ISSUER_BETA",
                    },
                ],
                "projected_positions": [
                    {
                        "security_id": "A",
                        "security_name": "Alpha Holdings",
                        "proposed_quantity": 15,
                        "issuer_id": "ISSUER_ALPHA",
                    },
                    {
                        "security_id": "B",
                        "security_name": "Beta Bonds",
                        "proposed_quantity": 5,
                        "issuer_id": "ISSUER_BETA",
                    },
                ],
                "top_n": 2,
            },
        }
    )
    response = (await calculate_concentration(request)).model_dump()
    assert response["source_service"] == "lotus-risk"
    assert response["risk_proxy"]["hhi_current"] == 5000.0
    assert response["risk_proxy"]["hhi_proposed"] == 6250.0
    assert response["risk_proxy"]["hhi_delta"] == 1250.0
    assert response["single_position_concentration"]["top_n"] == 2
    assert response["single_position_concentration"]["top_position_weight_current"] == 0.5
    assert response["single_position_concentration"]["top_position_weight_proposed"] == 0.75
    assert response["single_position_concentration"]["top_position_current"] == {
        "security_id": "B",
        "security_name": "Beta Bonds",
        "weight": 0.5,
    }
    assert response["single_position_concentration"]["top_position_proposed"] == {
        "security_id": "A",
        "security_name": "Alpha Holdings",
        "weight": 0.75,
    }
    assert response["issuer_concentration"]["top_issuer_current"] == {
        "issuer_id": "ISSUER_BETA",
        "issuer_name": None,
        "weight": 0.5,
    }
    assert response["issuer_concentration"]["top_issuer_proposed"] == {
        "issuer_id": "ISSUER_ALPHA",
        "issuer_name": None,
        "weight": 0.75,
    }
    assert response["issuer_concentration"]["coverage_ratio_current"] == 1.0
    assert response["issuer_concentration"]["coverage_ratio_proposed"] == 1.0
    assert response["issuer_concentration"]["uncovered_position_count_current"] == 0
    assert response["issuer_concentration"]["uncovered_position_count_proposed"] == 0
    assert response["metadata"]["lineage_version"] == "risk_audit_lineage.v1"
    assert response["metadata"]["request_fingerprint"].startswith("sha256:")
    assert response["metadata"]["source_services"] == ["lotus-risk"]
    assert response["metadata"]["upstream_request_fingerprints"] == {}
    assert {
        key: value
        for key, value in response["metadata"].items()
        if key
        not in {
            "lineage_version",
            "request_fingerprint",
            "source_services",
            "upstream_request_fingerprints",
        }
    } == {
        "as_of_date": None,
        "portfolio_id": None,
        "simulation_session_id": None,
        "simulation_session_version": None,
        "session_expires_at": None,
        "issuer_grouping_level": "ultimate_parent",
        "enrichment_policy": "merge_caller_then_core",
        "include_cash_positions": None,
        "include_zero_quantity_positions": None,
        "calculation_supportability": {
            "state": "ready",
            "reason": "calculation_complete",
            "freshness_bucket": "unknown",
            "metric_labels": RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS,
            "degraded_metric_count": 0,
            "empty_period_count": 0,
            "evaluated_period_count": 1,
        },
    }


@pytest.mark.asyncio
async def test_calculate_concentration_rejects_legacy_payload() -> None:
    with pytest.raises(ValidationError):
        ConcentrationRequest.model_validate(
            {
                "current_positions": [{"security_id": "A", "quantity": 10}],
                "projected_positions": [{"security_id": "A", "proposed_quantity": 10}],
            }
        )


@pytest.mark.asyncio
async def test_calculate_concentration_falls_back_to_current_when_no_projected() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateless",
            "stateless_input": {"current_positions": [{"security_id": "A", "quantity": 10}]},
        }
    )
    response = (await calculate_concentration(request)).model_dump()
    assert response["risk_proxy"]["hhi_current"] == 10000.0
    assert response["risk_proxy"]["hhi_proposed"] == 10000.0
    assert response["risk_proxy"]["hhi_delta"] == 0.0
    assert response["issuer_concentration"]["uncovered_position_count_current"] == 1
    assert response["issuer_concentration"]["uncovered_position_count_proposed"] == 1
    assert response["metadata"]["issuer_grouping_level"] == "ultimate_parent"
    assert response["metadata"]["enrichment_policy"] == "merge_caller_then_core"
    assert response["metadata"]["calculation_supportability"] == {
        "state": "degraded",
        "reason": "calculation_quality_issue",
        "freshness_bucket": "unknown",
        "metric_labels": RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS,
        "degraded_metric_count": 1,
        "empty_period_count": 0,
        "evaluated_period_count": 1,
    }
