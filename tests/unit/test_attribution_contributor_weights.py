"""`weight_average` must be a weight, and `marginal_contribution` per unit of it.

The decomposition builds a `group_matrix` of `weight x metric` -- the right input
for the covariance against the metric series, and the wrong thing to average when
the question is "what was this group's weight". The column mean of that matrix is
`E[w * r]`: smaller than the weight by a factor of the mean return, and negative
whenever the mean return is. Reading the weight from there made a declared 60%
position report `-0.0000757`, and `marginal_contribution = component / weight`
inherited the error, coming out scaled by `1 / E[r]` -- a quantity with no
meaning, unstable in sign, and unbounded as the mean return approaches zero.

The published example was right about the intent all along: `weight_average`
0.245 with `component` 0.0192 and `marginal` 0.0784, and 0.0192 / 0.245 = 0.0784.
`test_attribution_example_reconciles` checks exactly those ratios and could not
see the defect, because every ratio it checks is internally consistent under
either reading. What it never asserted is that `weight_average` is a *weight*.

So these tests pin the value against a known input rather than against the
service's own other outputs, and the load-bearing one varies the mean return --
the dimension the ratio tests hold fixed, and the only one that separates the two
readings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.contracts.attribution import AttributionType
from app.services.attribution_calculation import (
    DecompositionRow,
    attribution_calculation_inputs,
    component_decomposition,
)

ANNUALIZATION_BASIS = 252
OBSERVATIONS = 500
#: Constant weights, so the textbook answers are exact: each group's component is
#: `w * annualised vol`, they sum to the total, and every marginal equals the
#: annualised vol itself.
WEIGHTS = {"TECH": 0.60, "FIN": 0.30, "UTIL": 0.10}


def _dates() -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=OBSERVATIONS, freq="B")


def _returns(*, mean: float, volatility: float = 0.011, seed: int = 20260907) -> pd.Series:
    """A return series with a chosen mean and volatility.

    Drawn once and then recentred, so two series built with different means are
    identical up to a constant shift -- the volatility, and therefore every risk
    figure derived from it, is held exactly equal.
    """
    rng = np.random.default_rng(seed)
    drawn = pd.Series(rng.normal(0.0, volatility, OBSERVATIONS), index=_dates())
    return drawn - drawn.mean() + mean


def _constant_weights(weights: dict[str, float], index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame({group: [w] * len(index) for group, w in weights.items()}, index=index)


def _rows(
    *,
    returns: pd.Series,
    exposure: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    benchmark_weights: pd.DataFrame | None = None,
    attribution_type: AttributionType = "TOTAL_RISK",
) -> tuple[list[DecompositionRow], float]:
    inputs = attribution_calculation_inputs(
        attribution_type=attribution_type,
        returns_series=returns,
        benchmark_series=(
            benchmark_returns if benchmark_returns is not None else pd.Series(dtype=float)
        ),
        exposure_weights=exposure,
        benchmark_weights=(
            benchmark_weights
            if benchmark_weights is not None
            else pd.DataFrame(index=returns.index)
        ),
        annualization_basis=ANNUALIZATION_BASIS,
    )
    assert inputs is not None
    rows = component_decomposition(
        group_matrix=inputs.group_matrix,
        weight_matrix=inputs.weight_matrix,
        metric_series=inputs.metric_series,
        contribution_denominator=inputs.risk_total,
        annualization_basis=ANNUALIZATION_BASIS,
    )
    return rows, inputs.risk_total


def _by_group(rows: list[DecompositionRow]) -> dict[str, DecompositionRow]:
    return {row["group_key"]: row for row in rows}


def test_weight_average_is_the_weight_that_was_supplied() -> None:
    """The assertion nothing made, and the whole defect.

    Pinned against the input rather than against another output, because every
    ratio between the service's own outputs held true under the wrong reading.
    """
    returns = _returns(mean=0.0005)
    rows, _ = _rows(returns=returns, exposure=_constant_weights(WEIGHTS, returns.index))

    for group, row in _by_group(rows).items():
        assert row["weight_average"] == pytest.approx(WEIGHTS[group], abs=1e-12)


def test_the_weight_does_not_move_with_the_mean_return() -> None:
    """The dimension the ratio tests hold fixed.

    Under the previous reading `weight_average` was `E[w * r]`, so shifting the
    mean return scaled every weight and flipped its sign at zero. Volatility is
    identical across these three series by construction, so a weight that moves
    at all is reading the return series.
    """
    weights_seen = []
    for mean in (-0.002, 0.0, 0.002):
        returns = _returns(mean=mean)
        rows, _ = _rows(returns=returns, exposure=_constant_weights(WEIGHTS, returns.index))
        weights_seen.append({g: row["weight_average"] for g, row in _by_group(rows).items()})

    negative, zero, positive = weights_seen
    assert negative == pytest.approx(WEIGHTS, abs=1e-12)
    assert zero == pytest.approx(WEIGHTS, abs=1e-12)
    assert positive == pytest.approx(WEIGHTS, abs=1e-12)


def test_marginal_contribution_does_not_move_with_the_mean_return() -> None:
    """The consequence a consumer would have rendered.

    `marginal = component / weight_average`, so the same error carried straight
    through: the previous reading produced marginals scaled by `1 / E[r]`, which
    for a mean daily return near zero is arbitrarily large and changes sign with
    it. The component and the total are unchanged across these series, so a
    marginal that moves is being divided by the wrong thing.
    """
    marginals_seen = []
    for mean in (-0.002, 0.0, 0.002):
        returns = _returns(mean=mean)
        rows, _ = _rows(returns=returns, exposure=_constant_weights(WEIGHTS, returns.index))
        marginals_seen.append(
            {g: row["marginal_contribution"] for g, row in _by_group(rows).items()}
        )

    first, *rest = marginals_seen
    for other in rest:
        assert other == pytest.approx(first, rel=1e-9)


def test_marginal_contribution_is_the_component_per_unit_of_weight() -> None:
    """Under constant weights every marginal equals the annualised volatility.

    `component_g = w_g * sigma` and `marginal_g = component_g / w_g`, so all three
    groups -- weighted 60/30/10 -- must report the same marginal. A marginal that
    varies with the weight is not a marginal.
    """
    returns = _returns(mean=0.0005)
    rows, risk_total = _rows(returns=returns, exposure=_constant_weights(WEIGHTS, returns.index))

    for group, row in _by_group(rows).items():
        component = row["component_contribution"]
        assert component is not None
        assert row["marginal_contribution"] == pytest.approx(component / WEIGHTS[group])
        assert row["marginal_contribution"] == pytest.approx(risk_total)


def test_components_reconcile_to_the_total_and_percents_to_one() -> None:
    """Unchanged by this fix, and asserted so it stays that way.

    The component is the covariance term and was always right; only the two
    fields derived from the weight were wrong. `percent_contribution` is a
    ratio despite its name -- these sum to 1.0, not 100.
    """
    returns = _returns(mean=0.0005)
    rows, risk_total = _rows(returns=returns, exposure=_constant_weights(WEIGHTS, returns.index))

    assert sum(float(row["component_contribution"] or 0.0) for row in rows) == pytest.approx(
        risk_total
    )
    assert sum(float(row["percent_contribution"] or 0.0) for row in rows) == pytest.approx(1.0)


def test_active_risk_reports_the_active_weight_not_the_portfolio_weight() -> None:
    """An active-risk marginal is per unit of active weight.

    The group matrix is built from `portfolio - benchmark`, so the weight the
    marginal divides by must be that difference -- including where it is
    negative, which is an underweight and a real position to report.
    """
    returns = _returns(mean=0.0005)
    benchmark = _returns(mean=0.0004, volatility=0.009, seed=31)
    portfolio_weights = _constant_weights({"TECH": 0.60, "FIN": 0.30, "UTIL": 0.10}, returns.index)
    benchmark_w = _constant_weights({"TECH": 0.40, "FIN": 0.45, "UTIL": 0.15}, returns.index)

    rows, _ = _rows(
        returns=returns,
        exposure=portfolio_weights,
        benchmark_returns=benchmark,
        benchmark_weights=benchmark_w,
        attribution_type="ACTIVE_RISK",
    )

    by_group = _by_group(rows)
    assert by_group["TECH"]["weight_average"] == pytest.approx(0.20, abs=1e-12)
    assert by_group["FIN"]["weight_average"] == pytest.approx(-0.15, abs=1e-12)
    assert by_group["UTIL"]["weight_average"] == pytest.approx(-0.05, abs=1e-12)


def test_a_group_held_exactly_at_benchmark_reports_no_marginal() -> None:
    """Zero active weight has no defined marginal, and must not be given one.

    This guard existed before but fired on `E[w * r]` being near zero, which is
    a statement about returns rather than about the position. Now it fires on
    the position actually being held at benchmark -- and a group at benchmark is
    a normal holding, not an error, so the row is still returned with its
    component.
    """
    returns = _returns(mean=0.0005)
    benchmark = _returns(mean=0.0004, volatility=0.009, seed=31)
    portfolio_weights = _constant_weights({"TECH": 0.60, "FIN": 0.40}, returns.index)
    benchmark_w = _constant_weights({"TECH": 0.20, "FIN": 0.40}, returns.index)

    rows, _ = _rows(
        returns=returns,
        exposure=portfolio_weights,
        benchmark_returns=benchmark,
        benchmark_weights=benchmark_w,
        attribution_type="ACTIVE_RISK",
    )

    by_group = _by_group(rows)
    assert by_group["FIN"]["weight_average"] == pytest.approx(0.0, abs=1e-12)
    assert by_group["FIN"]["marginal_contribution"] is None
    assert by_group["FIN"]["component_contribution"] is not None
    assert by_group["TECH"]["marginal_contribution"] is not None
