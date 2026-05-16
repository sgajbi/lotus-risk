from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.contracts.risk import ReturnPoint
from app.services.calculation_supportability import (
    supportability_from_attribution_results,
    supportability_from_concentration_response,
    supportability_from_period_results,
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
