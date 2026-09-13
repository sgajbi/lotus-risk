"""Empirical TOTAL_RISK proof for lotus-risk#291.

The golden fixture holds the weight paths and the portfolio return path IDENTICAL across
two scenarios and varies ONLY the per-group return series, so the new evidence is the
only free variable. Expected components were computed independently with stdlib
statistics (ddof=1 sample covariance/stdev, annualization sqrt(252)) from the same
fixture numbers -- never by reading the service's own output back. Group returns are
constructed so that sum(w_g * r_g) reconciles exactly to the portfolio return on every
date, which also makes the components sum exactly to the decomposed risk total.

The engine works in decimal units (percentage points / 100), so the independent
percentage-point expectations are divided by 100 here; percent contributions are
scale-invariant and used as computed.
"""

from __future__ import annotations

import datetime as dt
import random
from collections.abc import Callable, Mapping
from typing import Any

import pytest

from app.contracts.attribution import (
    AttributionContributor,
    AttributionInputMode,
    AttributionOptions,
    AttributionSetResult,
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionResponse,
    HistoricalAttributionStatelessInput,
)
from app.contracts.risk import ReturnPoint, RiskRequestPeriod, RiskRequestScope
from app.services.attribution_engine import calculate_historical_attribution
from app.services.attribution_group_evidence import (
    FLAG_GROUP_UNIVERSE_INCOMPLETE,
    FLAG_PERIOD_MISSING,
    FLAG_RECONCILIATION_BREACH,
    FLAG_TRUNCATED,
    GroupEvidencePack,
    parse_group_evidence,
)
from app.upstream_errors import UpstreamServiceError

DATES = [
    dt.date(2026, 4, 6),
    dt.date(2026, 4, 7),
    dt.date(2026, 4, 8),
    dt.date(2026, 4, 9),
    dt.date(2026, 4, 10),
    dt.date(2026, 4, 13),
    dt.date(2026, 4, 14),
    dt.date(2026, 4, 15),
]

# Weight paths (ratios), drifting over time, identical in both scenarios.
W_EQUITY = [0.60, 0.61, 0.59, 0.62, 0.63, 0.58, 0.60, 0.61]
W_FIXED = [0.30, 0.29, 0.31, 0.28, 0.27, 0.32, 0.30, 0.29]
W_CASH = [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10]

# Portfolio return path in percentage points, identical in both scenarios.
PORTFOLIO_PP = [-2.00, 1.00, 3.00, -1.00, 0.00, 2.00, -0.50, 1.50]

# Scenario A group returns (pp): equity heterogeneous, cash exactly zero (a zero-mean
# group), fixed_income derived so the evidence reconciles exactly per date.
A_EQUITY = [-3.50, 2.20, 4.10, -2.30, 0.90, 3.10, -1.40, 2.50]
A_FIXED = [
    0.3333333333,
    -1.1793103448,
    1.8741935484,
    1.5214285714,
    -2.1,
    0.63125,
    1.1333333333,
    -0.0862068966,
]

# Scenario B: different equity path (lower dispersion), same weights, same portfolio.
B_EQUITY = [-1.20, 0.40, 1.90, -0.20, -0.80, 0.70, 0.30, 0.10]
B_FIXED = [
    -4.2666666667,
    2.6068965517,
    6.0612903226,
    -3.1285714286,
    1.8666666667,
    4.98125,
    -2.2666666667,
    4.9620689655,
]

ZERO_CASH = [0.0] * 8

# Independent expectations in DECIMAL units (percentage-point expectations / 100).
EXPECTED_RISK_TOTAL = 0.26495282599
EXPECTED_A = {"equity": 0.256610208802, "fixed_income": 0.008342617188, "cash": 0.0}
EXPECTED_B = {"equity": 0.076802351226, "fixed_income": 0.188150474764, "cash": 0.0}
EXPECTED_PERCENT_A = {"equity": 0.9685128205, "fixed_income": 0.0314871795, "cash": 0.0}
EXPECTED_PERCENT_B = {"equity": 0.2898717949, "fixed_income": 0.7101282051, "cash": 0.0}
# The weight proxy never reads group returns: identical in both scenarios, with a
# phantom contribution for the all-zero-return cash sleeve.
EXPECTED_PROXY = {"equity": 0.157816773019, "fixed_income": 0.080640770372, "cash": 0.026495282599}

ABS_TOL = 2e-9


def _portfolio_points() -> list[ReturnPoint]:
    return [
        ReturnPoint(date=day, value=value) for day, value in zip(DATES, PORTFOLIO_PP, strict=True)
    ]


def _series_points(weights: list[float], returns_pp: list[float]) -> list[dict[str, Any]]:
    return [
        {
            "date": day.isoformat(),
            "return_pct": value,
            "portfolio_weight_pct": weight * 100.0,
        }
        for day, weight, value in zip(DATES, weights, returns_pp, strict=True)
    ]


def _evidence_row(
    group_key: str,
    weights: list[float],
    returns_pp: list[float],
    *,
    currency: str = "USD",
    dimension_field: str = "sector",
) -> dict[str, Any]:
    return {
        "key": {dimension_field: group_key},
        "contribution": 0.0,
        "weight_avg": sum(weights) / len(weights) * 100.0,
        "is_other": False,
        "group_return": {
            "status": "READY",
            "period_return_pct": 0.0,
            "currency": currency,
            "return_basis": "SOURCE_POSITION_VALUATION_TWR",
            "weight_basis": "BEGINNING_CAPITAL_RATIO",
            "series": _series_points(weights, returns_pp),
            "reason": None,
        },
    }


def _contribution_response(
    rows: list[dict[str, Any]], *, dimension_field: str = "sector"
) -> dict[str, Any]:
    return {
        "results_by_period": {
            "EXPLICIT": {"levels": [{"level": 1, "name": dimension_field, "rows": rows}]}
        }
    }


def _scenario_rows(equity_pp: list[float], fixed_pp: list[float]) -> list[dict[str, Any]]:
    return [
        _evidence_row("equity", W_EQUITY, equity_pp),
        _evidence_row("fixed_income", W_FIXED, fixed_pp),
        _evidence_row("cash", W_CASH, ZERO_CASH),
    ]


def _pack(
    response: dict[str, Any],
    *,
    expected_currency: str | None = "USD",
    expected_group_key_by_source_key: Mapping[str, str] | None = None,
    grouping_dimension: GroupingDimension = "SECTOR",
    dimension_field: str = "sector",
) -> GroupEvidencePack:
    if expected_group_key_by_source_key is None:
        results = response.get("results_by_period")
        period = results.get("EXPLICIT") if isinstance(results, Mapping) else None
        levels = period.get("levels", []) if isinstance(period, Mapping) else []
        rows = levels[0].get("rows", []) if levels and isinstance(levels[0], dict) else []
        expected_group_key_by_source_key = {
            str(row["key"][dimension_field]): str(row["key"][dimension_field])
            for row in rows
            if isinstance(row, dict)
            and not row.get("is_other")
            and isinstance(row.get("key"), dict)
            and row["key"].get(dimension_field) is not None
        }
    return parse_group_evidence(
        response,
        grouping_dimension=grouping_dimension,
        dimension_field=dimension_field,
        expected_currency=expected_currency,
        portfolio_returns=_portfolio_points(),
        expected_group_key_by_source_key=expected_group_key_by_source_key,
    )


def _stateless_input() -> HistoricalAttributionStatelessInput:
    exposure = [
        ExposurePoint(
            date=day,
            grouping_dimension="SECTOR",
            group_key=group_key,
            group_label=None,
            weight=weight_path[index],
        )
        for index, day in enumerate(DATES)
        for group_key, weight_path in (
            ("equity", W_EQUITY),
            ("fixed_income", W_FIXED),
            ("cash", W_CASH),
        )
    ]
    return HistoricalAttributionStatelessInput(
        scope=RiskRequestScope(as_of_date=DATES[-1], net_or_gross="NET"),
        periods=[
            RiskRequestPeriod(type="EXPLICIT", name="WINDOW", from_date=DATES[0], to_date=DATES[-1])
        ],
        returns=_portfolio_points(),
        benchmark_returns=[],
        exposure_history=exposure,
        benchmark_exposure_history=[],
        attribution_options=AttributionOptions(
            attribution_types=["TOTAL_RISK"],
            metrics=["VOLATILITY"],
            grouping_dimensions=["SECTOR"],
            annualization_basis=252,
        ),
    )


def _attribution_response(
    pack: GroupEvidencePack | None = None,
) -> HistoricalAttributionResponse:
    evidence: dict[str, dict[GroupingDimension, GroupEvidencePack]] | None = (
        {"WINDOW": {"SECTOR": pack}} if pack is not None else None
    )
    return calculate_historical_attribution(
        _stateless_input(),
        input_mode=AttributionInputMode.STATEFUL,
        group_evidence=evidence,
    )


def _contributors_by_key(
    response: HistoricalAttributionResponse,
) -> tuple[AttributionSetResult, dict[str, AttributionContributor]]:
    attribution_set = response.results["WINDOW"].attribution_sets[0]
    return attribution_set, {c.group_key: c for c in attribution_set.contributors}


@pytest.mark.parametrize(
    ("equity_pp", "fixed_pp", "expected", "expected_percent"),
    [
        (A_EQUITY, A_FIXED, EXPECTED_A, EXPECTED_PERCENT_A),
        (B_EQUITY, B_FIXED, EXPECTED_B, EXPECTED_PERCENT_B),
    ],
    ids=["scenario_a", "scenario_b"],
)
def test_empirical_components_match_independent_expectations(
    equity_pp: list[float],
    fixed_pp: list[float],
    expected: dict[str, float],
    expected_percent: dict[str, float],
) -> None:
    pack = _pack(_contribution_response(_scenario_rows(equity_pp, fixed_pp)))
    assert pack.empirical

    response = _attribution_response(pack)
    attribution_set, contributors = _contributors_by_key(response)

    assert attribution_set.risk_basis == "empirical_group_returns"
    assert attribution_set.total_value == pytest.approx(EXPECTED_RISK_TOTAL, abs=ABS_TOL)
    for group_key, expected_component in expected.items():
        assert contributors[group_key].component_contribution == pytest.approx(
            expected_component, abs=ABS_TOL
        ), group_key
        assert contributors[group_key].percent_contribution == pytest.approx(
            expected_percent[group_key], abs=ABS_TOL
        ), group_key
    # Exact per-date reconciliation makes the components sum exactly to the risk total.
    assert attribution_set.reconciled_sum == pytest.approx(EXPECTED_RISK_TOTAL, abs=ABS_TOL)
    # Empirical weight averages come from the producer's observed weights.
    assert contributors["equity"].weight_average == pytest.approx(
        sum(W_EQUITY) / len(W_EQUITY), abs=ABS_TOL
    )
    # All calculated sets are empirical: the structural limitation no longer composes.
    supportability = response.metadata.calculation_supportability
    assert supportability.state == "ready"
    assert supportability.reason == "calculation_complete"


def test_empirical_discriminates_where_the_weight_proxy_cannot() -> None:
    pack_a = _pack(_contribution_response(_scenario_rows(A_EQUITY, A_FIXED)))
    pack_b = _pack(_contribution_response(_scenario_rows(B_EQUITY, B_FIXED)))
    _, contributors_a = _contributors_by_key(_attribution_response(pack_a))
    _, contributors_b = _contributors_by_key(_attribution_response(pack_b))
    for group_key in ("equity", "fixed_income"):
        component_a = contributors_a[group_key].component_contribution
        component_b = contributors_b[group_key].component_contribution
        assert component_a is not None and component_b is not None, group_key
        assert abs(component_a - component_b) > 1e-6, group_key

    # Identical weights and portfolio path: the proxy cannot tell A from B, and it
    # attributes phantom risk to the all-zero-return cash sleeve.
    proxy_set, proxy_contributors = _contributors_by_key(_attribution_response(None))
    assert proxy_set.risk_basis == "weight_proxy"
    for group_key, expected_component in EXPECTED_PROXY.items():
        assert proxy_contributors[group_key].component_contribution == pytest.approx(
            expected_component, abs=ABS_TOL
        ), group_key
    proxy_response = _attribution_response(None)
    assert proxy_response.metadata.calculation_supportability.state == "degraded"
    assert (
        proxy_response.metadata.calculation_supportability.reason
        == "group_return_series_unavailable"
    )


def test_shuffled_valid_rows_and_series_reproduce_exact_outputs() -> None:
    rows = _scenario_rows(A_EQUITY, A_FIXED)
    shuffled = [dict(row) for row in rows]
    rng = random.Random(291)
    rng.shuffle(shuffled)
    for row in shuffled:
        row["group_return"] = dict(row["group_return"])
        series = list(row["group_return"]["series"])
        rng.shuffle(series)
        row["group_return"]["series"] = series

    expected_universe = {"equity": "equity", "fixed_income": "fixed_income", "cash": "cash"}
    baseline = _attribution_response(
        _pack(
            _contribution_response(rows),
            expected_group_key_by_source_key=expected_universe,
        )
    )
    reshuffled = _attribution_response(
        _pack(
            _contribution_response(shuffled),
            expected_group_key_by_source_key=expected_universe,
        )
    )
    assert reshuffled.results["WINDOW"] == baseline.results["WINDOW"]


def test_explicit_zero_weight_is_authoritative_zero_but_an_absent_date_is_unknown() -> None:
    # Explicit zero-weight observations are supplied evidence: fully empirical, and the
    # zero-return zero-mean cash sleeve contributes exactly nothing.
    expected_universe = {"equity": "equity", "fixed_income": "fixed_income", "cash": "cash"}
    complete = _pack(
        _contribution_response(_scenario_rows(A_EQUITY, A_FIXED)),
        expected_group_key_by_source_key=expected_universe,
    )
    assert complete.empirical
    _, contributors = _contributors_by_key(_attribution_response(complete))
    assert contributors["cash"].component_contribution == pytest.approx(0.0, abs=1e-12)

    # A complete source universe may also explicitly carry a zero-exposure group.
    # It is a supported economic fact, unlike omission of the same group.
    zero_exposure_rows = _scenario_rows(A_EQUITY, A_FIXED)
    for observation in zero_exposure_rows[2]["group_return"]["series"]:
        observation["portfolio_weight_pct"] = 0.0
    zero_exposure = _pack(
        _contribution_response(zero_exposure_rows),
        expected_group_key_by_source_key=expected_universe,
    )
    assert zero_exposure.empirical
    assert _contributors_by_key(_attribution_response(zero_exposure))[1][
        "cash"
    ].component_contribution == pytest.approx(0.0, abs=1e-12)

    # The same evidence with one cash date ABSENT is unknown coverage, not zero: the
    # pack degrades with the bounded calendar flag and the set keeps the weight proxy.
    rows = _scenario_rows(A_EQUITY, A_FIXED)
    cash_series = rows[2]["group_return"]["series"]
    del cash_series[4]  # 2026-04-10 becomes unknown for cash
    partial = _pack(_contribution_response(rows))
    assert not partial.empirical
    assert partial.degradation_flags == ("group_return_evidence:calendar_incomplete",)

    degraded_set, _ = _contributors_by_key(_attribution_response(partial))
    assert degraded_set.risk_basis == "weight_proxy"
    assert "group_return_evidence:calendar_incomplete" in degraded_set.quality_flags


def test_omitted_zero_return_or_offsetting_group_never_promotes_empirical_evidence() -> None:
    """A source omission is not detected by reconciliation when its contribution is zero.

    The second variant represents offsetting omitted groups: regardless of whether their
    missing weighted returns would cancel, the Core-sourced universe is authoritative.
    """
    full_universe = {"equity": "equity", "fixed_income": "fixed_income", "cash": "cash"}
    rows_without_cash = _scenario_rows(A_EQUITY, A_FIXED)[:2]
    zero_return_omission = _pack(
        _contribution_response(rows_without_cash),
        expected_group_key_by_source_key=full_universe,
    )
    assert zero_return_omission.degradation_flags == (FLAG_GROUP_UNIVERSE_INCOMPLETE,)
    assert not zero_return_omission.empirical
    assert (
        _contributors_by_key(_attribution_response(zero_return_omission))[0].risk_basis
        == "weight_proxy"
    )

    anchor_weights = [0.8] * len(DATES)
    offset_weights = [0.1] * len(DATES)
    anchor_returns = [value / 0.8 for value in PORTFOLIO_PP]
    offset_returns = [0.75] * len(DATES)
    complete_offsetting_rows = [
        _evidence_row("anchor", anchor_weights, anchor_returns),
        _evidence_row("offset_gain", offset_weights, offset_returns),
        _evidence_row("offset_loss", offset_weights, [-value for value in offset_returns]),
    ]
    assert all(
        sum(weight * group_return for weight, group_return in zip(weights, returns, strict=True))
        == pytest.approx(portfolio_return)
        for weights, returns, portfolio_return in zip(
            zip(anchor_weights, offset_weights, offset_weights, strict=True),
            zip(anchor_returns, offset_returns, [-value for value in offset_returns], strict=True),
            PORTFOLIO_PP,
            strict=True,
        )
    )
    rows_without_offsetting_groups = complete_offsetting_rows[:1]
    offsetting_omission = _pack(
        _contribution_response(rows_without_offsetting_groups),
        expected_group_key_by_source_key={
            "anchor": "anchor",
            "offset_gain": "offset_gain",
            "offset_loss": "offset_loss",
        },
    )
    assert offsetting_omission.degradation_flags == (FLAG_GROUP_UNIVERSE_INCOMPLETE,)
    assert not offsetting_omission.empirical


def test_missing_date_with_coincidentally_passing_reconciliation_still_degrades() -> None:
    """The dropped cash observation had zero return, so every per-date sum is unchanged
    -- reconciliation would pass -- yet the absence is unknown coverage and the set must
    stay degraded. Reconciliation passing is not completeness proof."""
    rows = _scenario_rows(A_EQUITY, A_FIXED)
    del rows[2]["group_return"]["series"][4]
    pack = _pack(_contribution_response(rows))
    assert FLAG_RECONCILIATION_BREACH not in pack.degradation_flags
    assert pack.degradation_flags == ("group_return_evidence:calendar_incomplete",)
    response = _attribution_response(pack)
    attribution_set = response.results["WINDOW"].attribution_sets[0]
    assert attribution_set.risk_basis == "weight_proxy"
    assert response.metadata.calculation_supportability.state == "degraded"


def test_reconciliation_breach_degrades_with_the_bounded_flag() -> None:
    rows = _scenario_rows(A_EQUITY, A_FIXED)
    rows[0]["group_return"]["series"][3]["return_pct"] += 0.05  # > 1bp decomposed drift
    pack = _pack(_contribution_response(rows))
    assert pack.degradation_flags == (FLAG_RECONCILIATION_BREACH,)
    attribution_set = _attribution_response(pack).results["WINDOW"].attribution_sets[0]
    assert attribution_set.risk_basis == "weight_proxy"


def test_declared_absences_map_to_bounded_flags() -> None:
    unavailable_row = {
        "key": {"sector": "equity"},
        "contribution": 0.0,
        "is_other": False,
        "group_return": {
            "status": "UNAVAILABLE",
            "currency": None,
            "series": [],
            "reason": "SOURCE_POSITION_VALUATION_ECONOMICS_INCOMPLETE",
        },
    }
    other_row = {
        "key": {"sector": "Other"},
        "contribution": 0.0,
        "is_other": True,
        "group_return": {"status": "UNAVAILABLE", "currency": None, "series": []},
    }
    pack = _pack(_contribution_response([unavailable_row, other_row]))
    assert set(pack.degradation_flags) == {
        "group_return_evidence:unavailable",
        FLAG_TRUNCATED,
    }

    empty = _pack({"results_by_period": {}})
    assert empty.degradation_flags == (FLAG_PERIOD_MISSING,)


@pytest.mark.parametrize(
    ("grouping_dimension", "dimension_field", "classified_key", "unknown_key"),
    [
        ("SECTOR", "sector", "SECTOR_TECH", "SECTOR_UNKNOWN"),
        ("ASSET_CLASS", "asset_class", "ASSET_CLASS_EQUITY", "ASSET_CLASS_UNKNOWN"),
    ],
)
def test_performance_unclassified_alias_maps_to_core_missing_dimension_identity(
    grouping_dimension: GroupingDimension,
    dimension_field: str,
    classified_key: str,
    unknown_key: str,
) -> None:
    """Performance's producer-owned missing-field bucket retains Core's UNKNOWN identity."""
    rows = [
        _evidence_row(
            "TECH" if grouping_dimension == "SECTOR" else "EQUITY",
            W_EQUITY,
            A_EQUITY,
            dimension_field=dimension_field,
        ),
        _evidence_row(
            "Unclassified",
            W_FIXED,
            A_FIXED,
            dimension_field=dimension_field,
        ),
        _evidence_row(
            "CASH",
            W_CASH,
            ZERO_CASH,
            dimension_field=dimension_field,
        ),
    ]
    expected_universe = {
        "TECH" if grouping_dimension == "SECTOR" else "EQUITY": classified_key,
        "UNKNOWN": unknown_key,
        "Unclassified": unknown_key,
        "CASH": f"{grouping_dimension}_CASH",
    }

    pack = _pack(
        _contribution_response(rows, dimension_field=dimension_field),
        expected_group_key_by_source_key=expected_universe,
        grouping_dimension=grouping_dimension,
        dimension_field=dimension_field,
    )

    assert pack.empirical
    assert set(pack.series_by_group) == {
        classified_key,
        unknown_key,
        f"{grouping_dimension}_CASH",
    }


@pytest.mark.parametrize(
    ("grouping_dimension", "dimension_field", "classified_key", "unknown_key"),
    [
        ("SECTOR", "sector", "SECTOR_TECH", "SECTOR_UNKNOWN"),
        ("ASSET_CLASS", "asset_class", "ASSET_CLASS_EQUITY", "ASSET_CLASS_UNKNOWN"),
    ],
)
def test_unclassified_declared_unavailable_degrades_without_losing_core_universe(
    grouping_dimension: GroupingDimension,
    dimension_field: str,
    classified_key: str,
    unknown_key: str,
) -> None:
    rows = [
        _evidence_row(
            "TECH" if grouping_dimension == "SECTOR" else "EQUITY",
            W_EQUITY,
            A_EQUITY,
            dimension_field=dimension_field,
        ),
        {
            "key": {dimension_field: "Unclassified"},
            "contribution": 0.0,
            "is_other": False,
            "group_return": {
                "status": "UNAVAILABLE",
                "currency": None,
                "series": [],
                "reason": "SOURCE_POSITION_VALUATION_ECONOMICS_INCOMPLETE",
            },
        },
        _evidence_row("CASH", W_CASH, ZERO_CASH, dimension_field=dimension_field),
    ]
    expected_universe = {
        "TECH" if grouping_dimension == "SECTOR" else "EQUITY": classified_key,
        "UNKNOWN": unknown_key,
        "Unclassified": unknown_key,
        "CASH": f"{grouping_dimension}_CASH",
    }

    pack = _pack(
        _contribution_response(rows, dimension_field=dimension_field),
        expected_group_key_by_source_key=expected_universe,
        grouping_dimension=grouping_dimension,
        dimension_field=dimension_field,
    )

    assert not pack.empirical
    assert pack.degradation_flags == ("group_return_evidence:unavailable",)


def test_foreign_producer_group_remains_an_invalid_response() -> None:
    rows = _scenario_rows(A_EQUITY, A_FIXED)
    rows[1]["key"] = {"sector": "FOREIGN"}
    with pytest.raises(UpstreamServiceError) as excinfo:
        _pack(
            _contribution_response(rows),
            expected_group_key_by_source_key={
                "equity": "SECTOR_EQUITY",
                "fixed_income": "SECTOR_FIXED_INCOME",
                "cash": "SECTOR_CASH",
            },
        )
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"results_by_period": []},
        {"results_by_period": {"EXPLICIT": []}},
        {"results_by_period": {"EXPLICIT": {}}},
        {"results_by_period": {"EXPLICIT": {"levels": {}}}},
        {"results_by_period": {"EXPLICIT": {"levels": []}}},
        {"results_by_period": {"EXPLICIT": {"levels": ["not-a-level"]}}},
        {
            "results_by_period": {
                "EXPLICIT": {"levels": [{"name": "sector", "rows": ["not-a-row"]}]}
            }
        },
    ],
)
def test_malformed_nested_contribution_containers_refuse_not_degrade(
    response: dict[str, Any],
) -> None:
    with pytest.raises(UpstreamServiceError) as excinfo:
        _pack(response)
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"


def test_non_object_row_mixed_with_valid_rows_is_refused_not_filtered() -> None:
    rows: list[Any] = _scenario_rows(A_EQUITY, A_FIXED)
    rows.insert(1, "not-a-row")
    with pytest.raises(UpstreamServiceError) as excinfo:
        _pack(_contribution_response(rows))
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"


def _malformed_case(mutate: Callable[[list[dict[str, Any]]], object]) -> dict[str, Any]:
    rows = _scenario_rows(A_EQUITY, A_FIXED)
    mutate(rows)
    return _contribution_response(rows)


@pytest.mark.parametrize(
    ("case_name", "mutate"),
    [
        (
            "nan_return",
            lambda rows: rows[0]["group_return"]["series"][2].__setitem__(
                "return_pct", float("nan")
            ),
        ),
        (
            "infinite_weight",
            lambda rows: rows[1]["group_return"]["series"][0].__setitem__(
                "portfolio_weight_pct", float("inf")
            ),
        ),
        (
            "non_numeric_return",
            lambda rows: rows[0]["group_return"]["series"][1].__setitem__("return_pct", "fast"),
        ),
        (
            "duplicate_series_date",
            lambda rows: rows[0]["group_return"]["series"].append(
                dict(rows[0]["group_return"]["series"][0])
            ),
        ),
        (
            "observation_outside_window",
            lambda rows: rows[0]["group_return"]["series"].append(
                {"date": "2026-04-20", "return_pct": 1.0, "portfolio_weight_pct": 60.0}
            ),
        ),
        (
            "duplicate_group_rows",
            lambda rows: rows.append(dict(rows[0])),
        ),
        (
            "unknown_status",
            lambda rows: rows[0]["group_return"].__setitem__("status", "PENDING"),
        ),
        (
            "missing_currency",
            lambda rows: rows[0]["group_return"].__setitem__("currency", None),
        ),
        (
            "unexpected_currency",
            lambda rows: rows[0]["group_return"].__setitem__("currency", "CHF"),
        ),
        (
            "missing_group_return",
            lambda rows: rows[0].__setitem__("group_return", None),
        ),
        (
            "unsupported_return_basis",
            lambda rows: rows[0]["group_return"].__setitem__("return_basis", "DERIVED"),
        ),
        (
            "missing_weight_basis",
            lambda rows: rows[0]["group_return"].__delitem__("weight_basis"),
        ),
    ],
)
def test_malformed_producer_evidence_is_refused_before_covariance(
    case_name: str, mutate: Callable[[list[dict[str, Any]]], object]
) -> None:
    with pytest.raises(UpstreamServiceError) as excinfo:
        _pack(_malformed_case(mutate))
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE", case_name


def test_duplicate_unavailable_group_rows_are_refused_not_collapsed() -> None:
    """Every hierarchy key is unique, even where the producer declares it unavailable."""
    rows = _scenario_rows(A_EQUITY, A_FIXED)
    unavailable = dict(rows[0])
    unavailable["group_return"] = {
        "status": "UNAVAILABLE",
        "currency": None,
        "series": [],
        "reason": "SOURCE_POSITION_VALUATION_ECONOMICS_INCOMPLETE",
    }
    rows[0] = unavailable
    rows.append(dict(unavailable))

    with pytest.raises(UpstreamServiceError) as excinfo:
        _pack(_contribution_response(rows))

    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"


def test_mixed_currencies_across_groups_are_refused_when_no_currency_was_pinned() -> None:
    rows = [
        _evidence_row("equity", W_EQUITY, A_EQUITY, currency="USD"),
        _evidence_row("fixed_income", W_FIXED, A_FIXED, currency="EUR"),
        _evidence_row("cash", W_CASH, ZERO_CASH, currency="USD"),
    ]
    with pytest.raises(UpstreamServiceError) as excinfo:
        _pack(_contribution_response(rows), expected_currency=None)
    assert excinfo.value.code == "UPSTREAM_INVALID_RESPONSE"


def test_active_risk_and_unsupported_metric_sets_never_use_group_evidence() -> None:
    pack = _pack(_contribution_response(_scenario_rows(A_EQUITY, A_FIXED)))
    stateless = _stateless_input()
    stateless = stateless.model_copy(
        update={
            "benchmark_returns": _portfolio_points(),
            "benchmark_exposure_history": stateless.exposure_history,
            "attribution_options": AttributionOptions(
                attribution_types=["TOTAL_RISK", "ACTIVE_RISK"],
                metrics=["VOLATILITY", "TRACKING_ERROR"],
                grouping_dimensions=["SECTOR"],
                annualization_basis=252,
            ),
        }
    )
    response = calculate_historical_attribution(
        stateless,
        input_mode=AttributionInputMode.STATEFUL,
        group_evidence={"WINDOW": {"SECTOR": pack}},
    )
    sets = {(s.attribution_type, s.metric): s for s in response.results["WINDOW"].attribution_sets}
    assert sets[("TOTAL_RISK", "VOLATILITY")].risk_basis == "empirical_group_returns"
    # ACTIVE_RISK has no benchmark-group return evidence and stays a weight proxy.
    assert sets[("ACTIVE_RISK", "TRACKING_ERROR")].risk_basis == "weight_proxy"
    # A response with any weight-proxy set keeps composing the structural limitation.
    assert response.metadata.calculation_supportability.state == "degraded"
    assert response.metadata.calculation_supportability.reason == "group_return_series_unavailable"


def test_conflicting_duplicate_exposure_weights_are_refused_not_averaged() -> None:
    """pivot_exposure silently averaged .25/.75 into .50 before #291; a contradictory
    pair of exposure facts is now refused. Identical duplicates still collapse."""
    import pandas as pd

    from app.services.attribution_source_frames import pivot_exposure

    def frame(weights: list[float]) -> pd.DataFrame:
        rows = [
            {
                "date": pd.Timestamp("2026-04-06"),
                "grouping_dimension": "SECTOR",
                "group_key": "equity",
                "group_label": None,
                "weight": weight,
            }
            for weight in weights
        ]
        return pd.DataFrame(rows)

    with pytest.raises(ValueError, match="conflicting duplicate exposure weights"):
        pivot_exposure(
            frame([0.25, 0.75]),
            start=pd.Timestamp("2026-04-01"),
            end=pd.Timestamp("2026-04-30"),
            grouping_dimension="SECTOR",
        )

    weights, _, _ = pivot_exposure(
        frame([0.25, 0.25]),
        start=pd.Timestamp("2026-04-01"),
        end=pd.Timestamp("2026-04-30"),
        grouping_dimension="SECTOR",
    )
    assert weights.iloc[0]["equity"] == pytest.approx(0.25)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_caller_supplied_nonfinite_economics_are_refused_at_the_contract(
    bad_value: float,
) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReturnPoint(date=DATES[0], value=bad_value)
    with pytest.raises(ValidationError):
        ExposurePoint(
            date=DATES[0],
            grouping_dimension="SECTOR",
            group_key="equity",
            weight=bad_value,
        )
