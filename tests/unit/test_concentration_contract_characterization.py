import pytest
from pydantic import ValidationError

from app.contracts.concentration import (
    ConcentrationRequest,
    EnrichmentPolicy,
    IssuerGroupingLevel,
)


def test_contract_defaults_for_issuer_controls() -> None:
    request = ConcentrationRequest.model_validate({"input_mode": "stateless"})
    assert request.issuer_grouping_level == IssuerGroupingLevel.ULTIMATE_PARENT
    assert request.enrichment_policy == EnrichmentPolicy.MERGE_CALLER_THEN_CORE


def test_contract_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        ConcentrationRequest.model_validate(
            {
                "input_mode": "stateless",
                "stateless_input": {},
                "legacy_field": "not-allowed",
            }
        )


def test_contract_parses_stateful_issuer_mappings_and_grouping_flags() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateful",
            "issuer_grouping_level": "legal_issuer",
            "enrichment_policy": "core_only",
            "stateful_input": {
                "portfolio_id": "DEMO_DPM_EUR_001",
                "as_of_date": "2026-02-27",
                "issuer_mappings": [
                    {
                        "security_id": "SEC_A",
                        "issuer_id": "ISSUER_A",
                        "ultimate_parent_issuer_id": "UPI_A",
                    }
                ],
            },
        }
    )
    assert request.issuer_grouping_level == IssuerGroupingLevel.LEGAL_ISSUER
    assert request.enrichment_policy == EnrichmentPolicy.CORE_ONLY
    assert request.stateful_input is not None
    assert request.stateful_input.issuer_mappings[0].security_id == "SEC_A"
