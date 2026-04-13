from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.live_portfolio_matrix import (
    CANONICAL_LIVE_AS_OF_DATE,
    CANONICAL_LIVE_PORTFOLIO_ID,
    LIVE_AS_OF_DATE_ENV,
    LIVE_PORTFOLIO_ID_ENV,
    LIVE_PORTFOLIO_MATRIX_JSON_ENV,
    REQUIRED_PORTFOLIO_ARCHETYPES,
    SUPPORTED_LIVE_ENDPOINTS,
    default_live_portfolio_case,
    live_as_of_date,
    live_portfolio_id,
    load_live_portfolio_matrix,
    missing_required_archetypes,
)


def test_default_live_portfolio_case_preserves_canonical_global_balanced_baseline() -> None:
    case = default_live_portfolio_case({})

    assert case.portfolio_id == CANONICAL_LIVE_PORTFOLIO_ID
    assert case.as_of_date == CANONICAL_LIVE_AS_OF_DATE
    assert case.archetype == "global_balanced"
    assert case.supported_endpoints == SUPPORTED_LIVE_ENDPOINTS
    assert missing_required_archetypes((case,)) == REQUIRED_PORTFOLIO_ARCHETYPES[1:]


def test_live_validation_matrix_doc_lists_code_required_archetypes() -> None:
    matrix_doc = Path("docs/operations/live-risk-validation-matrix.md").read_text(encoding="utf-8")

    assert CANONICAL_LIVE_PORTFOLIO_ID in matrix_doc
    for archetype in REQUIRED_PORTFOLIO_ARCHETYPES:
        assert archetype in matrix_doc


def test_default_live_portfolio_case_honors_existing_single_portfolio_overrides() -> None:
    env = {
        LIVE_PORTFOLIO_ID_ENV: "PB_TEST_EQUITY_001",
        LIVE_AS_OF_DATE_ENV: "2026-04-30",
    }

    assert live_portfolio_id(env) == "PB_TEST_EQUITY_001"
    assert live_as_of_date(env) == "2026-04-30"

    case = default_live_portfolio_case(env)

    assert case.portfolio_id == "PB_TEST_EQUITY_001"
    assert case.as_of_date == "2026-04-30"
    assert case.archetype == "global_balanced"


def test_live_portfolio_matrix_json_parses_bank_archetype_cases() -> None:
    matrix = [
        {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "archetype": "global_balanced",
            "label": "Global balanced",
            "as_of_date": "2026-03-31",
        },
        {
            "portfolio_id": "PB_SG_EQUITY_001",
            "archetype": "equity_heavy",
            "label": "Equity-heavy discretionary portfolio",
            "supported_endpoints": ["risk/calculate", "drawdown"],
            "supportability_note": "seeded for returns-only validation",
        },
    ]

    cases = load_live_portfolio_matrix({LIVE_PORTFOLIO_MATRIX_JSON_ENV: json.dumps(matrix)})

    assert [case.portfolio_id for case in cases] == [
        "PB_SG_GLOBAL_BAL_001",
        "PB_SG_EQUITY_001",
    ]
    assert cases[1].supported_endpoints == ("risk/calculate", "drawdown")
    assert cases[1].supportability_note == "seeded for returns-only validation"
    assert "equity_heavy" not in missing_required_archetypes(cases)
    assert "fixed_income_heavy" in missing_required_archetypes(cases)


@pytest.mark.parametrize(
    ("raw_value", "expected_message"),
    [
        ("not-json", "valid JSON"),
        (json.dumps({}), "JSON array"),
        (json.dumps([]), "at least one portfolio"),
        (json.dumps([{"portfolio_id": "PB_001"}]), "archetype"),
        (
            json.dumps([{"portfolio_id": "PB_001", "archetype": "crypto_only"}]),
            "unsupported live portfolio archetype",
        ),
        (
            json.dumps(
                [
                    {
                        "portfolio_id": "PB_001",
                        "archetype": "global_balanced",
                        "supported_endpoints": ["risk/calculate", "not-real"],
                    }
                ]
            ),
            "unsupported live validation endpoints",
        ),
    ],
)
def test_live_portfolio_matrix_json_rejects_ambiguous_or_unsupported_cases(
    raw_value: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        load_live_portfolio_matrix({LIVE_PORTFOLIO_MATRIX_JSON_ENV: raw_value})
