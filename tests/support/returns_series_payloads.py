from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_DEFAULT_CALCULATION_ID = "00000000-0000-4000-8000-000000000001"
_DEFAULT_INPUT_FINGERPRINT = "sha256:" + "1" * 64
_DEFAULT_CALCULATION_HASH = "sha256:" + "2" * 64


def build_return_rows(rows: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"date": date, "return_value": return_value} for date, return_value in rows]


def build_returns_series_response(
    *,
    portfolio_returns: Iterable[tuple[str, str]],
    benchmark_returns: Iterable[tuple[str, str]] | None = None,
    risk_free_returns: Iterable[tuple[str, str]] | None = None,
    portfolio_id: str = "DEMO_DPM_EUR_001",
    as_of_date: str | None = None,
    resolved_start_date: str | None = None,
    resolved_end_date: str | None = None,
    resolved_period_label: str | None = None,
    frequency: str = "DAILY",
    metric_basis: str = "NET",
    calculation_id: str = _DEFAULT_CALCULATION_ID,
    input_fingerprint: str = _DEFAULT_INPUT_FINGERPRINT,
    calculation_hash: str = _DEFAULT_CALCULATION_HASH,
    freshness: str = "current",
    requested_points: int | None = None,
    returned_points: int | None = None,
    missing_points: int = 0,
) -> dict[str, Any]:
    """Build a schema-faithful Performance returns-series fixture.

    Stateful Risk consumers must test the producer response they actually
    consume, not a series-only shortcut that omits source identity and quality.
    An empty qualified series remains useful for unrelated consumer fixtures;
    the production parser decides whether a particular operation requires
    portfolio observations.
    """
    portfolio_rows = list(portfolio_returns)
    resolved_as_of_date = as_of_date or max(
        (row[0] for row in portfolio_rows), default="2026-01-01"
    )
    resolved_returned_points = (
        returned_points if returned_points is not None else len(portfolio_rows)
    )
    resolved_requested_points = (
        requested_points
        if requested_points is not None
        else resolved_returned_points + missing_points
    )
    series: dict[str, list[dict[str, str]]] = {
        "portfolio_returns": build_return_rows(portfolio_rows),
    }
    if benchmark_returns is not None:
        series["benchmark_returns"] = build_return_rows(benchmark_returns)
    if risk_free_returns is not None:
        series["risk_free_returns"] = build_return_rows(risk_free_returns)
    return {
        "calculation_id": calculation_id,
        "source_service": "lotus-performance",
        "contract_version": "v1",
        "portfolio_id": portfolio_id,
        "as_of_date": resolved_as_of_date,
        "frequency": frequency,
        "metric_basis": metric_basis,
        "resolved_window": {
            "start_date": resolved_start_date or f"{resolved_as_of_date[:4]}-01-01",
            "end_date": resolved_end_date or resolved_as_of_date,
            "resolved_period_label": resolved_period_label,
        },
        "series": series,
        "provenance": {
            "input_mode": "stateful",
            "input_fingerprint": input_fingerprint,
            "calculation_hash": calculation_hash,
        },
        "diagnostics": {
            "coverage": {
                "requested_points": resolved_requested_points,
                "returned_points": resolved_returned_points,
                "missing_points": missing_points,
                "coverage_ratio": (
                    1.0
                    if resolved_requested_points == 0
                    else resolved_returned_points / resolved_requested_points
                ),
            },
            "freshness": freshness,
        },
        "metadata": {},
    }


RISK_STATEFUL_RETURNS = (
    ("2025-01-02", "0.0100"),
    ("2025-01-03", "0.0200"),
    ("2025-01-06", "-0.0100"),
    ("2025-01-07", "0.0050"),
)

RISK_STATEFUL_BENCHMARK_RETURNS = (
    ("2025-01-02", "0.0090"),
    ("2025-01-03", "0.0150"),
    ("2025-01-06", "-0.0080"),
    ("2025-01-07", "0.0040"),
)

JAN_2026_PORTFOLIO_RETURNS = (
    ("2026-01-02", "0.0100"),
    ("2026-01-05", "-0.0200"),
    ("2026-01-06", "0.0050"),
)

JAN_2026_DRAWDOWN_BENCHMARK_RETURNS = (
    ("2026-01-02", "0.0070"),
    ("2026-01-05", "-0.0100"),
    ("2026-01-06", "0.0040"),
)

JAN_2026_ROLLING_BENCHMARK_RETURNS = (
    ("2026-01-02", "0.0080"),
    ("2026-01-05", "-0.0150"),
    ("2026-01-06", "0.0040"),
)

JAN_2026_RISK_FREE_RETURNS = (
    ("2026-01-02", "0.0001"),
    ("2026-01-05", "0.0001"),
    ("2026-01-06", "0.0001"),
)
