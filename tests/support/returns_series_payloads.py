from __future__ import annotations

from typing import Iterable


def build_return_rows(rows: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"date": date, "return_value": return_value} for date, return_value in rows]


def build_returns_series_response(
    *,
    portfolio_returns: Iterable[tuple[str, str]],
    benchmark_returns: Iterable[tuple[str, str]] | None = None,
    risk_free_returns: Iterable[tuple[str, str]] | None = None,
) -> dict[str, dict[str, list[dict[str, str]]]]:
    series: dict[str, list[dict[str, str]]] = {
        "portfolio_returns": build_return_rows(portfolio_returns),
    }
    if benchmark_returns is not None:
        series["benchmark_returns"] = build_return_rows(benchmark_returns)
    if risk_free_returns is not None:
        series["risk_free_returns"] = build_return_rows(risk_free_returns)
    return {"series": series}


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
    ("2026-01-03", "-0.0200"),
    ("2026-01-04", "0.0050"),
)

JAN_2026_DRAWDOWN_BENCHMARK_RETURNS = (
    ("2026-01-02", "0.0070"),
    ("2026-01-03", "-0.0100"),
    ("2026-01-04", "0.0040"),
)

JAN_2026_ROLLING_BENCHMARK_RETURNS = (
    ("2026-01-02", "0.0080"),
    ("2026-01-03", "-0.0150"),
    ("2026-01-04", "0.0040"),
)

JAN_2026_RISK_FREE_RETURNS = (
    ("2026-01-02", "0.0001"),
    ("2026-01-03", "0.0001"),
    ("2026-01-04", "0.0001"),
)
