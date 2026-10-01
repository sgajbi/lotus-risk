from __future__ import annotations

from collections.abc import Sequence
from math import sqrt


def wealth_drawdown(return_series: Sequence[float]) -> list[float]:
    """Calculate drawdown from the unit wealth present before the first return."""
    wealth = 1.0
    running_peak = 1.0
    drawdowns: list[float] = []
    for daily_return in return_series:
        wealth *= 1.0 + daily_return
        running_peak = max(running_peak, wealth)
        drawdowns.append(wealth / running_peak - 1.0)
    return drawdowns


def max_drawdown(drawdowns: Sequence[float]) -> float:
    return min(drawdowns) if drawdowns else 0.0


def ulcer_index(drawdowns: Sequence[float]) -> float:
    if not drawdowns:
        return 0.0
    return sqrt(sum(value * value for value in drawdowns) / len(drawdowns))


def time_under_water(drawdowns: Sequence[float]) -> int:
    return sum(1 for value in drawdowns if value < 0.0)
