"""Admission boundary for Performance's v1 portfolio/benchmark group economics.

The producer owns source returns and weights. Risk owns the independent scope,
calendar and arithmetic checks before those facts reach tracking-error covariance.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.contracts.attribution import ExposurePoint, GroupingDimension
from app.contracts.risk import ReturnPoint
from app.integrations.upstream_operations import LOTUS_PERFORMANCE_GROUP_RETURN_EVIDENCE_OPERATION
from app.upstream_errors import invalid_upstream_payload, missing_upstream_data

TOLERANCE = Decimal("0.000001")
RETURN_BASIS = "SOURCE_POSITION_AND_BENCHMARK_COMPONENT_GROSS_TWR"
VALUATION_BASIS = "SOURCE_REPORTED_BEGINNING_AND_ENDING_MARKET_VALUES"
WEIGHT_BASIS = "SIGNED_BEGINNING_CAPITAL_AND_BENCHMARK_BOP_WEIGHT"


def _invalid(message: str) -> Exception:
    return invalid_upstream_payload(
        service="lotus-performance",
        operation=LOTUS_PERFORMANCE_GROUP_RETURN_EVIDENCE_OPERATION,
        message=f"group-return evidence: {message}",
    )


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise _invalid(f"missing or invalid {field}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _invalid(f"invalid {field}") from None
    if not result.is_finite():
        raise _invalid(f"non-finite {field}")
    return result


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise _invalid(f"invalid {field}")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _invalid(f"invalid {field}") from None


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _invalid(f"missing {field} object")
    return value


def _rows(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise _invalid(f"missing {field} rows")
    return value


@dataclass(frozen=True)
class ActiveGroupObservation:
    observation_date: date
    active_contribution: Decimal
    active_weight: Decimal


@dataclass(frozen=True)
class ActiveGroupEvidence:
    observations_by_group: Mapping[str, tuple[ActiveGroupObservation, ...]]
    source_cut_id: str
    benchmark_id: str
    reporting_currency: str


def active_group_key_by_source_id(
    *,
    exposure_history: Sequence[ExposurePoint],
    benchmark_exposure_history: Sequence[ExposurePoint],
    grouping_dimension: GroupingDimension,
    start_date: date,
    end_date: date,
) -> dict[str, str]:
    """Bind the producer's source labels to Risk's admitted contributor identities."""
    result: dict[str, str] = {}
    for point in [*exposure_history, *benchmark_exposure_history]:
        if (
            point.grouping_dimension != grouping_dimension
            or not start_date <= point.date <= end_date
        ):
            continue
        label = point.group_label
        if not isinstance(label, str) or not label.strip():
            raise _invalid("active exposure group lacks a source classification label")
        source_id = f"{grouping_dimension}:{'_'.join(label.casefold().split())}"
        existing = result.setdefault(source_id, point.group_key)
        if existing != point.group_key:
            raise _invalid("active exposure group source identity is ambiguous")
    return result


def _source_group_identity(dimension: GroupingDimension, label: str) -> str:
    return f"{dimension}:{'_'.join(label.casefold().split())}"


def _validated_scope(
    response: Mapping[str, Any],
    request: Mapping[str, Any],
    grouping_dimension: GroupingDimension,
    expected_benchmark_id: str | None,
) -> str:
    for field, expected in (
        ("contract_version", "v1"),
        ("calculation_id", request["calculation_id"]),
        ("portfolio_id", request["portfolio_id"]),
        ("as_of_date", request["as_of_date"]),
        ("window", request["window"]),
        ("grouping_dimension", grouping_dimension),
        ("reporting_currency", request["reporting_currency"]),
        ("return_basis", RETURN_BASIS),
        ("valuation_basis", VALUATION_BASIS),
        ("weight_basis", WEIGHT_BASIS),
    ):
        if response.get(field) != expected:
            raise _invalid(f"{field} does not match the admitted request or v1 contract")
    benchmark_id = response.get("benchmark_id")
    if not isinstance(benchmark_id, str) or not benchmark_id.strip():
        raise _invalid("missing benchmark_id")
    if expected_benchmark_id is None or benchmark_id != expected_benchmark_id:
        raise _invalid("group-return benchmark_id differs from admitted exposure source")
    return benchmark_id


def _validated_coverage(response: Mapping[str, Any], request: Mapping[str, Any]) -> set[date]:
    coverage = _mapping(response.get("coverage"), "coverage")
    if coverage.get("status") != "COMPLETE":
        raise missing_upstream_data(
            service="lotus-performance",
            operation=LOTUS_PERFORMANCE_GROUP_RETURN_EVIDENCE_OPERATION,
            message="group-return evidence reports incomplete coverage",
        )
    tolerance = _decimal(coverage.get("reconciliation_tolerance"), "reconciliation_tolerance")
    if coverage.get("reason_codes") != [] or not Decimal(0) <= tolerance <= TOLERANCE:
        raise _invalid("coverage contradicts the complete v1 contract")
    raw_dates = _rows(coverage.get("observed_dates"), "observed_dates")
    observed_dates = [_date(value, "observed_dates") for value in raw_dates]
    if len(set(observed_dates)) != len(observed_dates) or observed_dates != sorted(observed_dates):
        raise _invalid("duplicate or unordered coverage dates")
    start = _date(request["window"]["start_date"], "window start")
    end = _date(request["window"]["end_date"], "window end")
    if any(day < start or day > end for day in observed_dates):
        raise _invalid("coverage date outside request window")
    return set(observed_dates)


def _validated_lineage(response: Mapping[str, Any], request: Mapping[str, Any]) -> str:
    lineage = _mapping(response.get("source_lineage"), "source_lineage")
    if (
        lineage.get("tenant_scope") != "ADMITTED_TENANT"
        or lineage.get("upstream_revision_status") != "NOT_PROVIDED_BY_SOURCE"
    ):
        raise _invalid("unsupported source lineage")
    if lineage.get("execution_id") != request["calculation_id"]:
        raise _invalid("execution lineage does not match request")
    source_cut_id = lineage.get("source_cut_id")
    if (
        not isinstance(source_cut_id, str)
        or len(source_cut_id) != 71
        or not source_cut_id.startswith("sha256:")
    ):
        raise _invalid("missing source-cut identity")
    try:
        bytes.fromhex(source_cut_id[7:])
    except ValueError:
        raise _invalid("invalid source-cut identity") from None
    for snapshot in _rows(lineage.get("snapshots"), "source snapshots"):
        _validate_snapshot(snapshot)
    return source_cut_id


def _validate_snapshot(snapshot: Any) -> None:
    item = _mapping(snapshot, "source snapshot")
    required = (
        "upstream_endpoint",
        "source_identifier",
        "as_of_date",
        "request_fingerprint",
        "response_fingerprint",
        "retrieval_status",
    )
    if not all(isinstance(item.get(key), str) and item[key] for key in required):
        raise _invalid("incomplete source snapshot")
    if not item["retrieval_status"].startswith("2"):
        raise _invalid("failed source snapshot")


def _validated_return_paths(
    portfolio_returns: Sequence[ReturnPoint],
    benchmark_returns: Sequence[ReturnPoint],
    observed_dates: set[date],
) -> tuple[dict[date, Decimal], dict[date, Decimal]]:
    portfolio = {
        point.date: _decimal(point.value, "portfolio return") / 100 for point in portfolio_returns
    }
    benchmark = {
        point.date: _decimal(point.value, "benchmark return") / 100 for point in benchmark_returns
    }
    if set(portfolio) != set(benchmark):
        raise missing_upstream_data(
            service="lotus-performance",
            operation=LOTUS_PERFORMANCE_GROUP_RETURN_EVIDENCE_OPERATION,
            message="portfolio and benchmark return calendars differ for active attribution",
        )
    if not portfolio or not set(portfolio).issubset(observed_dates):
        raise _invalid("coverage omits a requested return date")
    return portfolio, benchmark


def _validated_aggregates(
    response: Mapping[str, Any],
    observed_dates: set[date],
) -> dict[date, Mapping[str, Any]]:
    aggregates: dict[date, Mapping[str, Any]] = {}
    for raw in _rows(response.get("aggregate_returns"), "aggregate_returns"):
        item = _mapping(raw, "aggregate return")
        day = _date(item.get("date"), "aggregate date")
        if day in aggregates:
            raise _invalid("duplicate aggregate date")
        aggregates[day] = item
    if set(aggregates) != observed_dates:
        raise _invalid("aggregate calendar differs from declared coverage")
    return aggregates


def _group_row_identity(
    item: Mapping[str, Any],
    aggregates: Mapping[date, Mapping[str, Any]],
    grouping_dimension: GroupingDimension,
    expected_group_key_by_source_id: Mapping[str, str],
) -> tuple[date, str, str, str]:
    day = _date(item.get("date"), "group date")
    source_id = item.get("group_id")
    label = item.get("group_label")
    if (
        day not in aggregates
        or not isinstance(source_id, str)
        or not isinstance(label, str)
        or not label.strip()
    ):
        raise _invalid("group row outside coverage or missing identity")
    if source_id != _source_group_identity(grouping_dimension, label):
        raise _invalid("group identity and label disagree")
    group_key = expected_group_key_by_source_id.get(source_id)
    if group_key is None:
        raise _invalid("group outside the admitted exposure universe")
    return day, source_id, label, group_key


def _validated_group_rows(
    response: Mapping[str, Any],
    aggregates: Mapping[date, Mapping[str, Any]],
    grouping_dimension: GroupingDimension,
    expected_group_key_by_source_id: Mapping[str, str],
) -> tuple[
    dict[str, dict[date, ActiveGroupObservation]],
    dict[date, Decimal],
    dict[date, Decimal],
    dict[date, Decimal],
]:
    by_group: dict[str, dict[date, ActiveGroupObservation]] = defaultdict(dict)
    active_sums: dict[date, Decimal] = defaultdict(Decimal)
    portfolio_sums: dict[date, Decimal] = defaultdict(Decimal)
    benchmark_sums: dict[date, Decimal] = defaultdict(Decimal)
    seen_rows: set[tuple[date, str]] = set()
    labels_by_id: dict[str, str] = {}
    for raw in _rows(response.get("rows"), "group evidence"):
        item = _mapping(raw, "group evidence row")
        day, source_id, label, group_key = _group_row_identity(
            item,
            aggregates,
            grouping_dimension,
            expected_group_key_by_source_id,
        )
        prior_label = labels_by_id.setdefault(source_id, label)
        if prior_label != label:
            raise _invalid("conflicting labels for one group identity")
        identity = (day, source_id)
        if identity in seen_rows:
            raise _invalid("duplicate group observation")
        seen_rows.add(identity)
        p_return = _decimal(item.get("portfolio_group_return"), "portfolio_group_return")
        b_return = _decimal(item.get("benchmark_group_return"), "benchmark_group_return")
        p_weight = _decimal(item.get("portfolio_weight"), "portfolio_weight")
        b_weight = _decimal(item.get("benchmark_weight"), "benchmark_weight")
        active = _decimal(item.get("active_contribution"), "active_contribution")
        if abs(active - (p_weight * p_return - b_weight * b_return)) > TOLERANCE:
            raise _invalid("active contribution does not match group economics")
        by_group[group_key][day] = ActiveGroupObservation(day, active, p_weight - b_weight)
        active_sums[day] += active
        portfolio_sums[day] += p_weight * p_return
        benchmark_sums[day] += b_weight * b_return
    if set(by_group) != set(expected_group_key_by_source_id.values()):
        raise _invalid("group evidence omits an admitted exposure group")
    return by_group, active_sums, portfolio_sums, benchmark_sums


def _validate_group_leg_reconciliation(
    aggregates: Mapping[date, Mapping[str, Any]],
    portfolio_sums: Mapping[date, Decimal],
    benchmark_sums: Mapping[date, Decimal],
) -> None:
    for day, item in aggregates.items():
        weighted_portfolio = _decimal(
            item.get("weighted_portfolio_return"), "weighted_portfolio_return"
        )
        portfolio = _decimal(item.get("portfolio_return"), "aggregate portfolio_return")
        benchmark = _decimal(item.get("benchmark_return"), "aggregate benchmark_return")
        if (
            abs(portfolio_sums[day] - weighted_portfolio) > TOLERANCE
            or abs(weighted_portfolio - portfolio) > TOLERANCE
            or abs(benchmark_sums[day] - benchmark) > TOLERANCE
        ):
            raise _invalid("group portfolio or benchmark returns do not reconcile")
        declared_delta = _decimal(
            item.get("portfolio_reconciliation_delta"), "portfolio_reconciliation_delta"
        )
        if abs(declared_delta - (weighted_portfolio - portfolio)) > TOLERANCE:
            raise _invalid("declared portfolio reconciliation delta disagrees with economics")


def _validate_daily_reconciliation(
    aggregates: Mapping[date, Mapping[str, Any]],
    active_sums: Mapping[date, Decimal],
    portfolio_by_date: Mapping[date, Decimal],
    benchmark_by_date: Mapping[date, Decimal],
) -> None:
    for day, item in aggregates.items():
        p_return = _decimal(item.get("portfolio_return"), "aggregate portfolio_return")
        b_return = _decimal(item.get("benchmark_return"), "aggregate benchmark_return")
        active = _decimal(item.get("active_return"), "aggregate active_return")
        if (
            abs(active - (p_return - b_return)) > TOLERANCE
            or abs(active_sums[day] - active) > TOLERANCE
        ):
            raise _invalid("group active contributions do not reconcile")
        for field in ("portfolio_reconciliation_delta", "group_active_contribution_delta"):
            if abs(_decimal(item.get(field), field)) > TOLERANCE:
                raise _invalid(f"{field} exceeds tolerance")
        if day in portfolio_by_date and (
            abs(p_return - portfolio_by_date[day]) > TOLERANCE
            or abs(b_return - benchmark_by_date[day]) > TOLERANCE
        ):
            raise _invalid("source returns do not match Risk's admitted return series")


def parse_active_group_evidence(
    response: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    expected_benchmark_id: str | None,
    grouping_dimension: GroupingDimension,
    expected_group_key_by_source_id: Mapping[str, str],
    portfolio_returns: Sequence[ReturnPoint],
    benchmark_returns: Sequence[ReturnPoint],
) -> ActiveGroupEvidence:
    """Require exact request/response scope and independent daily reconciliation.

    Source rows are decimal return ratios. Risk's return points are percentage
    points, so only the comparison converts units; covariance stays in ratios.
    """
    benchmark_id = _validated_scope(response, request, grouping_dimension, expected_benchmark_id)
    observed_dates = _validated_coverage(response, request)
    source_cut_id = _validated_lineage(response, request)

    portfolio_by_date, benchmark_by_date = _validated_return_paths(
        portfolio_returns,
        benchmark_returns,
        observed_dates,
    )
    aggregates = _validated_aggregates(response, observed_dates)
    by_group, active_sums, portfolio_sums, benchmark_sums = _validated_group_rows(
        response,
        aggregates,
        grouping_dimension,
        expected_group_key_by_source_id,
    )
    _validate_group_leg_reconciliation(aggregates, portfolio_sums, benchmark_sums)
    _validate_daily_reconciliation(
        aggregates,
        active_sums,
        portfolio_by_date,
        benchmark_by_date,
    )
    required_dates = sorted(portfolio_by_date)

    return ActiveGroupEvidence(
        observations_by_group={
            key: tuple(
                by_group[key].get(day, ActiveGroupObservation(day, Decimal(0), Decimal(0)))
                for day in sorted(required_dates)
            )
            for key in sorted(by_group)
        },
        source_cut_id=source_cut_id,
        benchmark_id=benchmark_id,
        reporting_currency=str(response["reporting_currency"]),
    )
