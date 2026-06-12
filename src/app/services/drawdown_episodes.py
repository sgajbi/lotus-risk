from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np


@dataclass
class EpisodeRecord:
    peak_date: date
    trough_date: date
    recovery_date: date | None
    depth: float
    days_to_trough: int
    days_to_recovery: int | None
    total_days: int
    is_recovered: bool


@dataclass(frozen=True)
class DrawdownExtremeFields:
    max_drawdown: float
    peak_date: date | None
    trough_date: date | None
    recovery_date: date | None
    is_recovered: bool
    days_to_trough: int
    days_to_recovery: int | None


@dataclass(frozen=True)
class _EpisodeBuildContext:
    dates: list[date]
    values: list[float]
    duration_unit: str


def duration_days(start: date, end: date, *, unit: str) -> int:
    if end < start:
        return 0
    if unit == "CALENDAR_DAYS":
        return (end - start).days
    return int(np.busday_count(start.isoformat(), end.isoformat()))


def build_episodes_from_values(
    *,
    dates: list[date],
    values: list[float],
    duration_unit: str,
) -> list[EpisodeRecord]:
    context = _EpisodeBuildContext(
        dates=dates,
        values=values,
        duration_unit=duration_unit,
    )
    episodes: list[EpisodeRecord] = []
    in_episode = False
    start_index = 0
    peak_date = dates[0]
    for idx, dd_value in enumerate(values):
        if not in_episode and dd_value < 0:
            in_episode = True
            start_index = idx
            peak_date = _episode_peak_date(dates, idx)
            continue
        if in_episode and dd_value >= 0:
            _append_episode_record(episodes, context, start_index, peak_date, idx)
            in_episode = False

    if in_episode:
        _append_episode_record(episodes, context, start_index, peak_date, None)
    return episodes


def _episode_peak_date(dates: list[date], index: int) -> date:
    return dates[index - 1] if index > 0 else dates[index]


def _append_episode_record(
    episodes: list[EpisodeRecord],
    context: _EpisodeBuildContext,
    start_index: int,
    peak_date: date,
    recovery_index: int | None,
) -> None:
    episodes.append(
        episode_record_from_segment(
            dates=context.dates,
            values=context.values,
            start_index=start_index,
            peak_date=peak_date,
            duration_unit=context.duration_unit,
            recovery_index=recovery_index,
        )
    )


def episode_record_from_segment(
    *,
    dates: list[date],
    values: list[float],
    start_index: int,
    peak_date: date,
    duration_unit: str,
    recovery_index: int | None,
) -> EpisodeRecord:
    end_index = recovery_index if recovery_index is not None else len(values) - 1
    segment_values = values[start_index : end_index + 1]
    trough_offset = int(np.argmin(segment_values))
    trough_index = start_index + trough_offset
    trough_date = dates[trough_index]
    recovery_date = dates[recovery_index] if recovery_index is not None else None
    terminal_date = recovery_date or dates[-1]
    depth = float(min(segment_values))
    return EpisodeRecord(
        peak_date=peak_date,
        trough_date=trough_date,
        recovery_date=recovery_date,
        depth=depth,
        days_to_trough=duration_days(peak_date, trough_date, unit=duration_unit),
        days_to_recovery=(
            duration_days(trough_date, recovery_date, unit=duration_unit)
            if recovery_date is not None
            else None
        ),
        total_days=duration_days(peak_date, terminal_date, unit=duration_unit),
        is_recovered=recovery_date is not None,
    )


def drawdown_extreme_fields(episodes: list[EpisodeRecord]) -> DrawdownExtremeFields:
    max_episode = min(episodes, key=lambda episode: episode.depth) if episodes else None
    if max_episode is None:
        return DrawdownExtremeFields(
            max_drawdown=0.0,
            peak_date=None,
            trough_date=None,
            recovery_date=None,
            is_recovered=True,
            days_to_trough=0,
            days_to_recovery=0,
        )
    return DrawdownExtremeFields(
        max_drawdown=max_episode.depth,
        peak_date=max_episode.peak_date,
        trough_date=max_episode.trough_date,
        recovery_date=max_episode.recovery_date,
        is_recovered=max_episode.is_recovered,
        days_to_trough=max_episode.days_to_trough,
        days_to_recovery=max_episode.days_to_recovery,
    )


__all__ = [
    "DrawdownExtremeFields",
    "EpisodeRecord",
    "build_episodes_from_values",
    "drawdown_extreme_fields",
    "duration_days",
    "episode_record_from_segment",
]
