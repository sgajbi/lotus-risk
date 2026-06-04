from __future__ import annotations

import datetime as dt

from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

from app.contracts.risk import ReturnPoint
from app.services.calculation_supportability import (
    default_calculation_supportability,
    supportability_from_attribution_results,
    supportability_from_concentration_response,
    supportability_from_period_results,
    supportability_from_risk_metric_results,
)


class _PeriodResult(BaseModel):
    portfolio_observation_count: int
    error: str | None = None


class _AttributionSet(BaseModel):
    quality_flags: list[str]


class _AttributionPeriodResult(BaseModel):
    attribution_sets: list[_AttributionSet]
    error: str | None = None


def test_period_supportability_reports_stale_ready_payload() -> None:
    supportability = supportability_from_period_results(
        returns=[ReturnPoint(date=dt.date(2026, 1, 2), value=1.2)],
        as_of_date=dt.date(2026, 1, 5),
        results={"YTD": _PeriodResult(portfolio_observation_count=1)},
    )

    assert supportability.state == "stale"
    assert supportability.reason == "stale_source_observations"
    assert supportability.freshness_bucket == "stale"
    assert supportability.evaluated_period_count == 1


def test_default_supportability_is_ready_with_unknown_freshness() -> None:
    supportability = default_calculation_supportability()

    assert supportability.state == "ready"
    assert supportability.reason == "calculation_complete"
    assert supportability.freshness_bucket == "unknown"


def test_period_supportability_reports_empty_period_without_result_errors() -> None:
    supportability = supportability_from_period_results(
        returns=[ReturnPoint(date=dt.date(2026, 1, 5), value=1.2)],
        as_of_date=dt.date(2026, 1, 5),
        results={"YTD": _PeriodResult(portfolio_observation_count=0)},
    )

    assert supportability.state == "empty"
    assert supportability.reason == "insufficient_observations"
    assert supportability.empty_period_count == 1


def test_period_supportability_prioritizes_benchmark_degradation() -> None:
    supportability = supportability_from_period_results(
        returns=[ReturnPoint(date=dt.date(2026, 1, 5), value=1.2)],
        as_of_date=dt.date(2026, 1, 5),
        results={
            "YTD": _PeriodResult(
                portfolio_observation_count=3,
                error="BENCHMARK_UNAVAILABLE",
            )
        },
    )

    assert supportability.state == "degraded"
    assert supportability.reason == "benchmark_unavailable"
    assert supportability.freshness_bucket == "current"
    assert supportability.degraded_metric_count == 1


def test_attribution_supportability_degrades_when_sets_emit_quality_flags() -> None:
    supportability = supportability_from_attribution_results(
        returns=[ReturnPoint(date=dt.date(2026, 1, 5), value=1.2)],
        as_of_date=dt.date(2026, 1, 5),
        results={
            "YTD": _AttributionPeriodResult(
                attribution_sets=[
                    _AttributionSet(quality_flags=[]),
                    _AttributionSet(quality_flags=["grouping:SECTOR:no_exposure_data"]),
                ],
            )
        },
    )

    assert supportability.state == "degraded"
    assert supportability.reason == "calculation_quality_issue"
    assert supportability.freshness_bucket == "current"
    assert supportability.degraded_metric_count == 1
    assert supportability.evaluated_period_count == 1


def test_attribution_supportability_ignores_non_sequence_attribution_sets() -> None:
    supportability = supportability_from_attribution_results(
        returns=[ReturnPoint(date=dt.date(2026, 1, 5), value=1.2)],
        as_of_date=dt.date(2026, 1, 5),
        results={"YTD": SimpleNamespace(portfolio_observation_count=1, attribution_sets=object())},
    )

    assert supportability.state == "ready"
    assert supportability.reason == "calculation_complete"


def test_risk_metric_supportability_counts_metric_errors_and_empty_periods() -> None:
    metric_with_error = SimpleNamespace(
        details={"error": "Benchmark returns required for benchmark-dependent metric"}
    )
    metric_without_mapping_details = SimpleNamespace(details=object())
    supportability = supportability_from_risk_metric_results(
        returns=[ReturnPoint(date=dt.date(2026, 1, 5), value=1.2)],
        as_of_date=dt.date(2026, 1, 5),
        results={
            "YTD": SimpleNamespace(
                portfolio_observation_count=1,
                metrics={
                    "BETA": metric_with_error,
                    "VOLATILITY": metric_without_mapping_details,
                },
            ),
            "MTD": SimpleNamespace(
                portfolio_observation_count=0,
                error="Insufficient data",
                metrics=cast_metrics_object(),
            ),
        },
    )

    assert supportability.state == "degraded"
    assert supportability.reason == "benchmark_unavailable"
    assert supportability.degraded_metric_count == 1
    assert supportability.empty_period_count == 1


def cast_metrics_object() -> Any:
    return object()


def test_concentration_supportability_reports_uncovered_issuer_mapping() -> None:
    supportability = supportability_from_concentration_response(
        covered_position_count_current=0,
        covered_position_count_proposed=0,
        total_position_count_current=2,
        total_position_count_proposed=2,
        issuer_note="issuer mapping unavailable for stateless payload",
    )

    assert supportability.state == "degraded"
    assert supportability.reason == "calculation_quality_issue"
    assert supportability.freshness_bucket == "unknown"
    assert supportability.degraded_metric_count == 1
