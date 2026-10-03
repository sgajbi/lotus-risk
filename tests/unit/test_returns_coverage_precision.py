from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.stateful_returns_source_evidence import StatefulReturnsSourceEvidence


def _evidence(requested: int, returned: int, ratio: Any) -> dict[str, Any]:
    return {
        "source_service": "lotus-performance",
        "calculation_id": "00000000-0000-4000-8000-000000000001",
        "contract_version": "v1",
        "input_fingerprint": "sha256:" + "1" * 64,
        "calculation_hash": "sha256:" + "2" * 64,
        "freshness": "current",
        "requested_points": requested,
        "returned_points": returned,
        "missing_points": requested - returned,
        "coverage_ratio": ratio,
    }


@pytest.mark.parametrize(
    ("requested", "returned", "wire_ratio"),
    [
        (270, 269, 0.9962963),
        (3, 1, 0.33333333),
        (3, 2, 0.66666667),
        (7, 6, 0.85714286),
        (0, 0, 1.0),
        (269, 269, 1.0),
    ],
)
@pytest.mark.parametrize("wire_is_string", [False, True])
def test_admits_eight_decimal_producer_coverage_without_rewriting_evidence(
    requested: int,
    returned: int,
    wire_ratio: float,
    wire_is_string: bool,
) -> None:
    wire_value = str(wire_ratio) if wire_is_string else wire_ratio
    result = StatefulReturnsSourceEvidence.model_validate(
        _evidence(requested, returned, wire_value)
    )
    assert result.coverage_ratio == wire_ratio
    assert result.missing_points == requested - returned
    assert result.returned_points == returned


@pytest.mark.parametrize(("requested", "returned"), [(270, 269), (3, 1), (7, 6)])
def test_preserves_unquantized_ratio_compatibility(requested: int, returned: int) -> None:
    ratio = float(Fraction(returned, requested))
    result = StatefulReturnsSourceEvidence.model_validate(_evidence(requested, returned, ratio))
    assert result.coverage_ratio == ratio


@pytest.mark.parametrize(
    "ratio",
    [
        0.90,
        0.99629629,
        0.99629631,
        0.9962963001,
        0.9962962999,
        -0.1,
        1.1,
        float("nan"),
        float("inf"),
        "not-a-ratio",
        None,
    ],
)
def test_refuses_false_or_malformed_ratios(ratio: Any) -> None:
    with pytest.raises(ValidationError):
        StatefulReturnsSourceEvidence.model_validate(_evidence(270, 269, ratio))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("missing_points", 0),
        ("returned_points", 271),
        ("requested_points", -1),
        ("freshness", "unknown"),
        ("source_service", "other-service"),
        ("calculation_id", "not-a-uuid"),
        ("input_fingerprint", "missing"),
    ],
)
def test_precision_compatibility_does_not_relax_source_qualification(
    field: str, value: Any
) -> None:
    evidence = _evidence(270, 269, 0.9962963)
    evidence[field] = value
    with pytest.raises(ValidationError):
        StatefulReturnsSourceEvidence.model_validate(evidence)


def test_zero_request_policy_requires_unit_coverage() -> None:
    with pytest.raises(ValidationError):
        StatefulReturnsSourceEvidence.model_validate(_evidence(0, 0, 0.0))


def test_precision_compatibility_requires_coverage_evidence() -> None:
    evidence = _evidence(270, 269, 0.9962963)
    del evidence["coverage_ratio"]
    with pytest.raises(ValidationError):
        StatefulReturnsSourceEvidence.model_validate(evidence)
