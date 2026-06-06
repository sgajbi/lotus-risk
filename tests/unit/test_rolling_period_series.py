import pytest

from app.contracts.rolling import RollingStatelessInput
from app.services.rolling_period_series import build_rolling_input_frames, rolling_period_series


def _rolling_input() -> RollingStatelessInput:
    return RollingStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-05", "net_or_gross": "NET"},
            "periods": [{"type": "EXPLICIT", "from_date": "2026-01-03", "to_date": "2026-01-05"}],
            "returns": [
                {"date": "2026-01-05", "value": 0.5},
                {"date": "2026-01-03", "value": 1.0},
                {"date": "2026-01-04", "value": -0.2},
                {"date": "2026-01-02", "value": 0.1},
            ],
            "benchmark_returns": [
                {"date": "2026-01-03", "value": 0.8},
                {"date": "2026-01-05", "value": 0.4},
            ],
            "risk_free_returns": [
                {"date": "2026-01-04", "value": 0.01},
                {"date": "2026-01-05", "value": 0.02},
            ],
            "rolling_options": {"window_lengths": [3], "metrics": ["ROLLING_VOLATILITY"]},
        }
    )


def test_build_rolling_input_frames_sorts_return_dates() -> None:
    frames = build_rolling_input_frames(_rolling_input())

    assert [index.date().isoformat() for index in frames.portfolio.index] == [
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
    ]
    assert [index.date().isoformat() for index in frames.benchmark.index] == [
        "2026-01-03",
        "2026-01-05",
    ]


def test_rolling_period_series_filters_and_converts_dependency_series() -> None:
    request = _rolling_input()
    frames = build_rolling_input_frames(request)

    period_series = rolling_period_series(
        frames=frames,
        request=request,
        period=request.periods[0],
        open_date=frames.portfolio.index.min().date(),
    )

    assert period_series.name == "EXPLICIT"
    assert [index.date().isoformat() for index in period_series.portfolio_pp.index] == [
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
    ]
    assert period_series.portfolio_decimal.iloc[0] == pytest.approx(0.01)
    assert period_series.benchmark_decimal.iloc[0] == pytest.approx(0.008)
    assert period_series.risk_free_decimal.iloc[-1] == pytest.approx(0.0002)
