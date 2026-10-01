from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from app.contracts.risk import RiskCalculationRequest
from app.contracts.risk_options import RiskOptions
from app.services.risk import calculation_orchestrator


@pytest.mark.parametrize(
    ("frequency", "override", "expected"),
    [
        ("DAILY", None, 252),
        ("WEEKLY", None, 52),
        ("MONTHLY", None, 12),
        ("MONTHLY", 260, 260),
    ],
)
def test_shared_risk_annualization_options(
    frequency: str, override: int | None, expected: int
) -> None:
    options = RiskOptions.model_validate({"frequency": frequency, "annualization_factor": override})
    assert calculation_orchestrator.annualization_factor_for_options(options) == expected


def test_period_calculation_reports_requested_metrics_through_timing_port() -> None:
    request = RiskCalculationRequest.model_validate(
        {
            "scope": {"as_of_date": "2026-01-03", "net_or_gross": "NET"},
            "portfolio_open_date": "2026-01-01",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY", "DRAWDOWN"],
            "returns": [
                {"date": "2026-01-01", "value": 1.0},
                {"date": "2026-01-02", "value": -0.5},
                {"date": "2026-01-03", "value": 0.25},
            ],
        }
    )
    observed_metrics: list[str] = []

    @contextmanager
    def observe_metric_duration(metric_name: str) -> Iterator[None]:
        observed_metrics.append(metric_name)
        yield

    returns_df, benchmark_df = calculation_orchestrator.resolve_return_frames(request)
    annual_factor = calculation_orchestrator.derive_annualization_factor(request)
    periodic_rf, periodic_mar = calculation_orchestrator.resolve_periodic_rates(
        request=request,
        annual_factor=annual_factor,
    )

    results = calculation_orchestrator.build_period_results(
        request,
        annual_factor=annual_factor,
        periodic_rf=periodic_rf,
        periodic_mar=periodic_mar,
        returns_df=returns_df,
        benchmark_df=benchmark_df,
        observe_metric_duration=observe_metric_duration,
    )

    assert set(results["YTD"].metrics) == {"VOLATILITY", "DRAWDOWN"}
    assert observed_metrics == ["VOLATILITY", "DRAWDOWN"]
