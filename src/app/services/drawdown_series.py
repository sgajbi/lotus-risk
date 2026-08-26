from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from typing import Any, cast

import numpy as np
import pandas as pd

from app.contracts.drawdown import DrawdownSummary, UnderwaterPoint
from app.services.drawdown_episodes import (
    DrawdownExtremeFields,
    EpisodeRecord,
    build_episodes_from_values,
    drawdown_extreme_fields,
    duration_days,
    episode_record_from_segment,
)


def _numeric_observation(raw: Any) -> float:
    return float(raw)


def _is_underwater(raw: object) -> bool:
    return _numeric_observation(raw) < 0


def drawdown_from_returns(returns: pd.Series) -> pd.Series:
    wealth = (1 + returns / 100.0).cumprod()
    running_peak = wealth.cummax()
    return wealth / running_peak - 1.0


def drawdown_summary(
    drawdown: pd.Series,
    *,
    alpha: float,
    duration_unit: str,
) -> tuple[DrawdownSummary, list[EpisodeRecord]]:
    if drawdown.empty:
        return empty_drawdown_summary(), []

    episodes = build_episodes(drawdown, duration_unit=duration_unit)
    depths = [episode.depth for episode in episodes]
    dar_value, cdar_value = tail_drawdown_risk(depths, alpha=alpha)
    extreme = drawdown_extreme_fields(episodes)

    summary = DrawdownSummary(
        max_drawdown=extreme.max_drawdown,
        max_drawdown_peak_date=extreme.peak_date,
        max_drawdown_trough_date=extreme.trough_date,
        max_drawdown_recovery_date=extreme.recovery_date,
        is_recovered=extreme.is_recovered,
        days_to_trough=extreme.days_to_trough,
        days_to_recovery=extreme.days_to_recovery,
        time_under_water_days=int(
            sum(1 for observation in drawdown if _is_underwater(observation))
        ),
        average_drawdown=average_drawdown(drawdown),
        ulcer_index=ulcer_index(drawdown),
        drawdown_at_risk_95=dar_value,
        conditional_drawdown_at_risk_95=cdar_value,
    )
    return summary, episodes


def to_underwater_series(drawdown: pd.Series) -> list[UnderwaterPoint]:
    points: list[UnderwaterPoint] = []
    for index, observation in drawdown.items():
        timestamp = cast(pd.Timestamp, index)
        numeric_observation = _numeric_observation(observation)
        points.append(UnderwaterPoint(date=timestamp.date(), drawdown=numeric_observation))
    return points


def build_episodes(drawdown: pd.Series, *, duration_unit: str) -> list[EpisodeRecord]:
    dates = [cast(pd.Timestamp, index).date() for index in drawdown.index]
    observations = [_numeric_observation(observation) for observation in drawdown]
    if not observations:
        return []
    return build_episodes_from_values(
        dates=dates,
        values=observations,
        duration_unit=duration_unit,
    )


def empty_drawdown_summary() -> DrawdownSummary:
    return DrawdownSummary(
        max_drawdown=None,
        max_drawdown_peak_date=None,
        max_drawdown_trough_date=None,
        max_drawdown_recovery_date=None,
        is_recovered=False,
        days_to_trough=None,
        days_to_recovery=None,
        time_under_water_days=0,
        average_drawdown=None,
        ulcer_index=None,
        drawdown_at_risk_95=None,
        conditional_drawdown_at_risk_95=None,
    )


episode_records_from_values = build_episodes_from_values


def tail_drawdown_risk(
    depths: Sequence[float], *, alpha: float
) -> tuple[float | None, float | None]:
    if not depths:
        return None, None
    quantile_result = np.quantile(np.array(depths), 1.0 - alpha, method="linear")
    dar_metric = _numeric_observation(quantile_result)
    worst_tail = [depth for depth in depths if depth <= dar_metric]
    cdar_metric = _numeric_observation(np.mean(worst_tail)) if worst_tail else None
    return dar_metric, cdar_metric


def average_drawdown(drawdown: pd.Series) -> float:
    underwater_observations = [
        _numeric_observation(observation) for observation in drawdown if _is_underwater(observation)
    ]
    return (
        _numeric_observation(np.mean(underwater_observations)) if underwater_observations else 0.0
    )


def ulcer_index(drawdown: pd.Series) -> float:
    observations = [_numeric_observation(observation) for observation in drawdown]
    mean_square = np.mean(np.square(np.array(observations)))
    return _numeric_observation(sqrt(_numeric_observation(mean_square)))


__all__ = [
    "DrawdownExtremeFields",
    "EpisodeRecord",
    "average_drawdown",
    "build_episodes",
    "drawdown_extreme_fields",
    "drawdown_from_returns",
    "drawdown_summary",
    "duration_days",
    "empty_drawdown_summary",
    "episode_record_from_segment",
    "episode_records_from_values",
    "tail_drawdown_risk",
    "to_underwater_series",
    "ulcer_index",
]
