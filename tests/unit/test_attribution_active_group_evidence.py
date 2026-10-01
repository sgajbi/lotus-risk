"""Independent financial and hostile-source admission proof for Risk #283."""

from __future__ import annotations

import asyncio
import copy
from datetime import date
from decimal import Decimal
from statistics import covariance, stdev
from typing import Any
from uuid import uuid4

import pandas as pd
import pytest

from app.contracts.attribution import ExposurePoint, HistoricalAttributionStatefulInput
from app.contracts.risk import ReturnPoint
from app.services.attribution_active_group_evidence import (
    ActiveGroupEvidence,
    active_group_key_by_source_id,
    parse_active_group_evidence,
)
from app.services.attribution_active_group_fetch import fetch_active_group_evidence
from app.services.attribution_calculation import (
    attribution_calculation_inputs,
    component_decomposition,
    empirical_active_risk_inputs,
)
from app.services.attribution_group_evidence import GroupEvidencePack
from app.services.attribution_group_evidence_lineage import canonical_group_evidence_payload
from app.upstream_errors import UpstreamServiceError
from tests.support.downstream_authority import admitted_test_authority

DATES = ["2026-04-06", "2026-04-07", "2026-04-08"]
P_A = [Decimal(".01"), Decimal("-.01"), Decimal(".02")]
P_B = [Decimal(0), Decimal(".02"), Decimal("-.01")]
B_A = [Decimal(".005"), Decimal(0), Decimal(".01")]
B_B = [Decimal(".01"), Decimal(".01"), Decimal("-.005")]
P_WEIGHT = [Decimal(".6"), Decimal(".4")]
B_WEIGHT = [Decimal(".5"), Decimal(".5")]
P_RETURN = [P_WEIGHT[0] * a + P_WEIGHT[1] * b for a, b in zip(P_A, P_B, strict=True)]
B_RETURN = [B_WEIGHT[0] * a + B_WEIGHT[1] * b for a, b in zip(B_A, B_B, strict=True)]
ACTIVE = [p - b for p, b in zip(P_RETURN, B_RETURN, strict=True)]
GROUP_A = [P_WEIGHT[0] * p - B_WEIGHT[0] * b for p, b in zip(P_A, B_A, strict=True)]
GROUP_B = [P_WEIGHT[1] * p - B_WEIGHT[1] * b for p, b in zip(P_B, B_B, strict=True)]


def _request() -> dict[str, Any]:
    return {
        "calculation_id": str(uuid4()),
        "portfolio_id": "portfolio-a",
        "as_of_date": DATES[-1],
        "window": {"start_date": DATES[0], "end_date": DATES[-1]},
        "grouping_dimension": "SECTOR",
        "reporting_currency": "USD",
    }


def _response(request: dict[str, Any]) -> dict[str, Any]:
    rows = []
    aggregates = []
    for index, day in enumerate(DATES):
        for label, p_return, b_return, p_weight, b_weight, active in (
            ("TECH", P_A[index], B_A[index], P_WEIGHT[0], B_WEIGHT[0], GROUP_A[index]),
            ("HEALTH", P_B[index], B_B[index], P_WEIGHT[1], B_WEIGHT[1], GROUP_B[index]),
        ):
            rows.append(
                {
                    "date": day,
                    "group_id": f"SECTOR:{label.casefold()}",
                    "group_label": label,
                    "portfolio_group_return": str(p_return),
                    "benchmark_group_return": str(b_return),
                    "portfolio_weight": str(p_weight),
                    "benchmark_weight": str(b_weight),
                    "active_contribution": str(active),
                }
            )
        aggregates.append(
            {
                "date": day,
                "portfolio_return": str(P_RETURN[index]),
                "weighted_portfolio_return": str(P_RETURN[index]),
                "portfolio_reconciliation_delta": "0",
                "benchmark_return": str(B_RETURN[index]),
                "active_return": str(ACTIVE[index]),
                "group_active_contribution_delta": "0",
            }
        )
    return {
        **request,
        "contract_version": "v1",
        "benchmark_id": "benchmark-a",
        "return_basis": "SOURCE_POSITION_AND_BENCHMARK_COMPONENT_GROSS_TWR",
        "valuation_basis": "SOURCE_REPORTED_BEGINNING_AND_ENDING_MARKET_VALUES",
        "weight_basis": "SIGNED_BEGINNING_CAPITAL_AND_BENCHMARK_BOP_WEIGHT",
        "coverage": {
            "status": "COMPLETE",
            "reason_codes": [],
            "observed_dates": DATES,
            "reconciliation_tolerance": "0.000001",
        },
        "aggregate_returns": aggregates,
        "rows": rows,
        "source_lineage": {
            "execution_id": request["calculation_id"],
            "tenant_scope": "ADMITTED_TENANT",
            "source_cut_id": "sha256:" + "a" * 64,
            "upstream_revision_status": "NOT_PROVIDED_BY_SOURCE",
            "snapshots": [
                {
                    "upstream_endpoint": "/integration/portfolios/p/analytics/position-timeseries",
                    "source_identifier": "portfolio-a",
                    "as_of_date": DATES[-1],
                    "request_fingerprint": "sha256:req",
                    "response_fingerprint": "sha256:resp",
                    "retrieval_status": "200",
                }
            ],
        },
    }


def _parse(response: dict[str, Any], request: dict[str, Any]) -> ActiveGroupEvidence:
    return parse_active_group_evidence(
        response,
        request=request,
        expected_benchmark_id="benchmark-a",
        grouping_dimension="SECTOR",
        expected_group_key_by_source_id={
            "SECTOR:tech": "SECTOR_TECH",
            "SECTOR:health": "SECTOR_HEALTH",
        },
        portfolio_returns=[
            ReturnPoint(date=date.fromisoformat(day), value=float(value * 100))
            for day, value in zip(DATES, P_RETURN, strict=True)
        ],
        benchmark_returns=[
            ReturnPoint(date=date.fromisoformat(day), value=float(value * 100))
            for day, value in zip(DATES, B_RETURN, strict=True)
        ],
    )


def test_signed_active_components_reconcile_to_independent_tracking_error() -> None:
    request = _request()
    evidence = _parse(_response(request), request)
    index = pd.to_datetime(DATES)
    inputs = empirical_active_risk_inputs(
        returns_series=pd.Series([float(value) for value in P_RETURN], index=index),
        benchmark_series=pd.Series([float(value) for value in B_RETURN], index=index),
        active_evidence=evidence,
        annualization_basis=252,
    )
    assert inputs is not None
    rows = component_decomposition(
        group_matrix=inputs.group_matrix,
        weight_matrix=inputs.weight_matrix,
        metric_series=inputs.metric_series,
        contribution_denominator=inputs.risk_total,
        annualization_basis=252,
    )
    components = {row["group_key"]: row["component_contribution"] for row in rows}
    expected_te = stdev([float(value) for value in ACTIVE]) * (252**0.5)
    expected_a = (
        covariance([float(value) for value in GROUP_A], [float(value) for value in ACTIVE])
        / stdev([float(value) for value in ACTIVE])
        * (252**0.5)
    )
    expected_b = (
        covariance([float(value) for value in GROUP_B], [float(value) for value in ACTIVE])
        / stdev([float(value) for value in ACTIVE])
        * (252**0.5)
    )
    assert inputs.risk_total == pytest.approx(expected_te, abs=1e-12)
    assert components["SECTOR_TECH"] == pytest.approx(expected_a, abs=1e-12)
    assert components["SECTOR_HEALTH"] == pytest.approx(expected_b, abs=1e-12)
    assert sum(value for value in components.values() if value is not None) == pytest.approx(
        expected_te, abs=1e-12
    )
    assert components["SECTOR_HEALTH"] is not None and components["SECTOR_HEALTH"] < 0
    # The old active-weight proxy sums to zero and leaves 100% of TE as residual.
    assert abs(expected_te) > 0.01


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_scope",
        "wrong_benchmark",
        "wrong_currency",
        "wrong_calendar",
        "duplicate_row",
        "label_conflict",
        "bad_arithmetic",
        "bad_source_return",
        "failed_snapshot",
        "missing_group",
        "foreign_group",
        "bad_cut",
        "nonhex_cut",
        "missing_benchmark",
        "wrong_execution",
        "wrong_economic_basis",
        "negative_tolerance",
        "oversized_tolerance",
        "coverage_reason",
        "unordered_dates",
        "out_of_window_date",
        "missing_snapshot",
        "incomplete_snapshot",
        "nonfinite_weight",
        "non_numeric_return",
        "boolean_weight",
        "aggregate_duplicate",
        "aggregate_missing",
        "unreconciled_active",
        "nonzero_reconciliation_delta",
        "wrong_group_identity",
        "row_outside_calendar",
        "foreign_group_with_matching_label",
        "foreign_tenant_lineage",
        "source_return_drift_with_reconciled_active",
        "null_aggregate_row",
        "null_group_row",
        "missing_coverage_object",
        "bad_observed_date",
    ],
)
def test_malformed_or_mismatched_source_cannot_reach_covariance(mutation: str) -> None:
    request = _request()
    response = copy.deepcopy(_response(request))
    if mutation == "wrong_scope":
        response["portfolio_id"] = "portfolio-b"
    elif mutation == "wrong_benchmark":
        response["benchmark_id"] = "benchmark-b"
    elif mutation == "wrong_currency":
        response["reporting_currency"] = "EUR"
    elif mutation == "wrong_calendar":
        response["coverage"]["observed_dates"] = DATES[:-1]
    elif mutation == "duplicate_row":
        response["rows"].append(copy.deepcopy(response["rows"][0]))
    elif mutation == "label_conflict":
        response["rows"][2]["group_label"] = "tech"
    elif mutation == "bad_arithmetic":
        response["rows"][0]["active_contribution"] = "0"
    elif mutation == "bad_source_return":
        response["aggregate_returns"][0]["portfolio_return"] = "0"
    elif mutation == "failed_snapshot":
        response["source_lineage"]["snapshots"][0]["retrieval_status"] = "500"
    elif mutation == "missing_group":
        response["rows"] = [row for row in response["rows"] if row["group_id"] != "SECTOR:health"]
    elif mutation == "foreign_group":
        response["rows"][0]["group_id"] = "SECTOR:foreign"
    elif mutation == "bad_cut":
        response["source_lineage"]["source_cut_id"] = "sha256:invalid"
    elif mutation == "nonhex_cut":
        response["source_lineage"]["source_cut_id"] = "sha256:" + "z" * 64
    elif mutation == "missing_benchmark":
        response.pop("benchmark_id")
    elif mutation == "wrong_execution":
        response["source_lineage"]["execution_id"] = str(uuid4())
    elif mutation == "wrong_economic_basis":
        response["return_basis"] = "PROXY"
    elif mutation == "negative_tolerance":
        response["coverage"]["reconciliation_tolerance"] = "-0.000001"
    elif mutation == "oversized_tolerance":
        response["coverage"]["reconciliation_tolerance"] = "0.1"
    elif mutation == "coverage_reason":
        response["coverage"]["reason_codes"] = ["MISSING_DAY"]
    elif mutation == "unordered_dates":
        response["coverage"]["observed_dates"] = list(reversed(DATES))
    elif mutation == "out_of_window_date":
        response["coverage"]["observed_dates"][0] = "2026-04-05"
    elif mutation == "missing_snapshot":
        response["source_lineage"]["snapshots"] = []
    elif mutation == "incomplete_snapshot":
        response["source_lineage"]["snapshots"][0].pop("response_fingerprint")
    elif mutation == "nonfinite_weight":
        response["rows"][0]["portfolio_weight"] = "NaN"
    elif mutation == "non_numeric_return":
        response["rows"][0]["portfolio_group_return"] = "broken"
    elif mutation == "boolean_weight":
        response["rows"][0]["benchmark_weight"] = True
    elif mutation == "aggregate_duplicate":
        response["aggregate_returns"].append(copy.deepcopy(response["aggregate_returns"][0]))
    elif mutation == "aggregate_missing":
        response["aggregate_returns"].pop()
    elif mutation == "unreconciled_active":
        response["aggregate_returns"][0]["active_return"] = "0"
    elif mutation == "nonzero_reconciliation_delta":
        response["aggregate_returns"][0]["portfolio_reconciliation_delta"] = "0.1"
    elif mutation == "wrong_group_identity":
        response["rows"][0]["group_id"] = "SECTOR:health"
    elif mutation == "row_outside_calendar":
        response["rows"][0]["date"] = "2026-04-05"
    elif mutation == "foreign_group_with_matching_label":
        response["rows"][0]["group_id"] = "SECTOR:foreign"
        response["rows"][0]["group_label"] = "FOREIGN"
    elif mutation == "foreign_tenant_lineage":
        response["source_lineage"]["tenant_scope"] = "UNKNOWN"
    elif mutation == "source_return_drift_with_reconciled_active":
        response["aggregate_returns"][0]["portfolio_return"] = str(P_RETURN[0] + Decimal(".01"))
        response["aggregate_returns"][0]["benchmark_return"] = str(B_RETURN[0] + Decimal(".01"))
    elif mutation == "null_aggregate_row":
        response["aggregate_returns"][0] = None
    elif mutation == "null_group_row":
        response["rows"][0] = None
    elif mutation == "missing_coverage_object":
        response["coverage"] = None
    elif mutation == "bad_observed_date":
        response["coverage"]["observed_dates"][0] = "not-a-date"
    with pytest.raises(UpstreamServiceError):
        _parse(response, request)


def test_declared_incomplete_coverage_is_data_gap_not_empirical_evidence() -> None:
    request = _request()
    response = _response(request)
    response["coverage"]["status"] = "INCOMPLETE"
    with pytest.raises(UpstreamServiceError):
        _parse(response, request)


def test_offsetting_portfolio_and_benchmark_leg_corruption_is_refused() -> None:
    request = _request()
    response = _response(request)
    row = response["rows"][0]
    # Both weighted legs drift by .006, so the row active contribution and
    # aggregate active return still reconcile. Each source leg must be checked.
    row["portfolio_group_return"] = str(P_A[0] + Decimal(".01"))
    row["benchmark_group_return"] = str(B_A[0] + Decimal(".012"))
    assert (
        P_WEIGHT[0] * Decimal(row["portfolio_group_return"])
        - B_WEIGHT[0] * Decimal(row["benchmark_group_return"])
        == GROUP_A[0]
    )
    with pytest.raises(UpstreamServiceError, match="group portfolio or benchmark"):
        _parse(response, request)


def test_admitted_exposure_labels_cannot_alias_distinct_risk_groups() -> None:
    first = ExposurePoint(
        date=date.fromisoformat(DATES[0]),
        grouping_dimension="SECTOR",
        group_key="SECTOR_TECH",
        group_label="Technology",
        weight=0.6,
    )
    later = first.model_copy(update={"date": date.fromisoformat(DATES[1])})
    other_dimension = first.model_copy(update={"grouping_dimension": "ASSET_CLASS"})
    outside_window = first.model_copy(update={"date": date(2026, 4, 9)})
    assert active_group_key_by_source_id(
        exposure_history=[first, later, other_dimension, outside_window],
        benchmark_exposure_history=[],
        grouping_dimension="SECTOR",
        start_date=date.fromisoformat(DATES[0]),
        end_date=date.fromisoformat(DATES[-1]),
    ) == {"SECTOR:technology": "SECTOR_TECH"}

    ambiguous = later.model_copy(update={"group_key": "SECTOR_OTHER"})
    with pytest.raises(UpstreamServiceError, match="ambiguous"):
        active_group_key_by_source_id(
            exposure_history=[first],
            benchmark_exposure_history=[ambiguous],
            grouping_dimension="SECTOR",
            start_date=date.fromisoformat(DATES[0]),
            end_date=date.fromisoformat(DATES[-1]),
        )
    with pytest.raises(UpstreamServiceError, match="classification label"):
        active_group_key_by_source_id(
            exposure_history=[first.model_copy(update={"group_label": None})],
            benchmark_exposure_history=[],
            grouping_dimension="SECTOR",
            start_date=date.fromisoformat(DATES[0]),
            end_date=date.fromisoformat(DATES[-1]),
        )


def test_portfolio_and_benchmark_return_calendars_must_match_before_covariance() -> None:
    request = _request()
    with pytest.raises(UpstreamServiceError) as excinfo:
        parse_active_group_evidence(
            _response(request),
            request=request,
            expected_benchmark_id="benchmark-a",
            grouping_dimension="SECTOR",
            expected_group_key_by_source_id={
                "SECTOR:tech": "SECTOR_TECH",
                "SECTOR:health": "SECTOR_HEALTH",
            },
            portfolio_returns=[
                ReturnPoint(date=date.fromisoformat(day), value=float(value * 100))
                for day, value in zip(DATES, P_RETURN, strict=True)
            ],
            benchmark_returns=[
                ReturnPoint(date=date.fromisoformat(day), value=float(value * 100))
                for day, value in zip(DATES[:-1], B_RETURN[:-1], strict=True)
            ],
        )
    assert excinfo.value.status_code == 424


def test_nonoverlapping_economic_calendars_do_not_produce_empirical_tracking_error() -> None:
    request = _request()
    evidence = _parse(_response(request), request)
    assert (
        empirical_active_risk_inputs(
            returns_series=pd.Series([0.01], index=pd.to_datetime([DATES[0]])),
            benchmark_series=pd.Series([0.008], index=pd.to_datetime(["2026-04-09"])),
            active_evidence=evidence,
            annualization_basis=252,
        )
        is None
    )
    # The legacy, explicitly qualified proxy must not invent an overlap either.
    assert (
        attribution_calculation_inputs(
            attribution_type="ACTIVE_RISK",
            returns_series=pd.Series([0.01], index=pd.to_datetime([DATES[0]])),
            benchmark_series=pd.Series([0.008], index=pd.to_datetime(["2026-04-09"])),
            exposure_weights=pd.DataFrame({"SECTOR_TECH": [0.6]}, index=pd.to_datetime([DATES[0]])),
            benchmark_weights=pd.DataFrame(
                {"SECTOR_TECH": [0.5]}, index=pd.to_datetime(["2026-04-09"])
            ),
            annualization_basis=252,
        )
        is None
    )


def test_unsupported_evidence_set_does_not_fingerprint_unused_group_facts() -> None:
    request = _request()
    pack = GroupEvidencePack(
        grouping_dimension="SECTOR",
        series_by_group={},
        degradation_flags=(),
        active_evidence=_parse(_response(request), request),
    )
    assert (
        canonical_group_evidence_payload(
            {"WINDOW": {"SECTOR": pack}},
            attribution_types=["TOTAL_RISK"],
            metrics=["TRACKING_ERROR"],
        )
        == {}
    )


@pytest.mark.parametrize("net_or_gross,currency", [("NET", "USD"), ("GROSS", None)])
def test_gross_source_is_never_called_for_unsupported_economic_basis(
    net_or_gross: str, currency: str | None
) -> None:
    stateful = HistoricalAttributionStatefulInput.model_validate(
        {
            "portfolio_id": "portfolio-a",
            "as_of_date": DATES[-1],
            "reporting_currency": currency,
            "net_or_gross": net_or_gross,
            "periods": [{"type": "YTD"}],
        }
    )
    with pytest.raises(ValueError, match="gross basis and explicit currency"):
        asyncio.run(
            fetch_active_group_evidence(
                stateful=stateful,
                performance_client=None,  # type: ignore[arg-type]
                portfolio_returns=[],
                benchmark_returns=[],
                exposure_history=[],
                benchmark_exposure_history=[],
                benchmark_identity=None,
                grouping_dimension="SECTOR",
                start_date=date.fromisoformat(DATES[0]),
                end_date=date.fromisoformat(DATES[-1]),
                authority=admitted_test_authority(),
            )
        )
