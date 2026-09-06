"""The published attribution example must obey the arithmetic it demonstrates.

An OpenAPI example is the first thing a consumer builds a fixture from, so an
example that contradicts the service teaches the wrong contract. The shipped one
stated `reconciled_sum` 0.0638 while its contributors' components summed to
0.0166 -- implying contributors are a top-N subset with the remainder folded
into `reconciled_sum`. They are not: the service returns every contributor and
`reconciled_sum` is exactly their sum, so a reconciliation view built on the
implied reading would be wrong about what `residual` represents.

These assertions restate the service's formulas against the example rather than
against a helper, so a drift in either direction fails here.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from app.contracts.attribution_examples import HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE

pytestmark = pytest.mark.unit

#: The example carries figures rounded for readability, so comparisons allow a
#: half-unit of the last published decimal place rather than exact equality.
TOLERANCE = 5e-5


def _attribution_sets() -> list[dict[str, Any]]:
    results = cast(dict[str, Any], HISTORICAL_ATTRIBUTION_RESPONSE_EXAMPLE["results"])
    return [
        attribution_set
        for period in results.values()
        for attribution_set in period["attribution_sets"]
    ]


def test_the_example_has_attribution_sets_to_check() -> None:
    """Guards the three tests below, which would pass vacuously on an empty list."""
    assert _attribution_sets()


def test_reconciled_sum_equals_every_contributor_component() -> None:
    """`reconciled_sum = sum(component_contribution)` over ALL contributors.

    Not a subset. This is the assertion the shipped example failed, and the one
    a consumer's reconciliation view depends on being true.
    """
    for attribution_set in _attribution_sets():
        components = sum(
            contributor["component_contribution"] for contributor in attribution_set["contributors"]
        )
        assert abs(components - attribution_set["reconciled_sum"]) < TOLERANCE, (
            f"contributors sum to {components}, "
            f"example claims reconciled_sum {attribution_set['reconciled_sum']}"
        )


def test_residual_is_total_minus_reconciled_sum() -> None:
    for attribution_set in _attribution_sets():
        expected = attribution_set["total_value"] - attribution_set["reconciled_sum"]
        assert abs(expected - attribution_set["residual"]) < TOLERANCE


def test_each_contributor_percent_and_marginal_follow_the_service_formulas() -> None:
    """`percent = component / total_value` and `marginal = component / weight_average`.

    Checked per contributor rather than in aggregate: a compensating pair of
    errors would survive a sum.
    """
    for attribution_set in _attribution_sets():
        total_value = attribution_set["total_value"]
        for contributor in attribution_set["contributors"]:
            component = contributor["component_contribution"]

            expected_percent = component / total_value
            assert abs(expected_percent - contributor["percent_contribution"]) < TOLERANCE, (
                f"{contributor['group_key']}: percent should be {expected_percent}"
            )

            expected_marginal = component / contributor["weight_average"]
            assert abs(expected_marginal - contributor["marginal_contribution"]) < TOLERANCE, (
                f"{contributor['group_key']}: marginal should be {expected_marginal}"
            )
