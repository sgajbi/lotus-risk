from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from collections.abc import Sequence
from typing import cast

import numpy as np
import pandas as pd

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownEpisode,
    DrawdownInputMode,
    DrawdownMetadata,
    DrawdownPeriodResult,
    RelativeDrawdownContext,
    DrawdownResponse,
    DrawdownStatelessInput,
    DrawdownSummary,
    RelativeDrawdownSummary,
    UnderwaterPoint,
)
from app.contracts.risk import RiskRequestPeriod
from app.contracts.risk import ReturnPoint
from app.services.risk_engine import _resolve_period


@dataclass
class _EpisodeRecord:
    peak_date: date
    trough_date: date
    recovery_date: date | None
    depth: float
    days_to_trough: int
    days_to_recovery: int | None
    total_days: int
    is_recovered: bool


def _duration_days(start: date, end: date, *, unit: str) -> int:
    if end < start:
        return 0
    if unit == "CALENDAR_DAYS":
        return (end - start).days
    return int(np.busday_count(start.isoformat(), end.isoformat()))


def _build_returns_df(returns: Sequence[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in returns])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _filter_period(df: pd.DataFrame, *, start: date, end: date) -> pd.Series:
    filtered = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)), "value"]
    return filtered


def _build_episodes(drawdown: pd.Series, *, duration_unit: str) -> list[_EpisodeRecord]:
    if drawdown.empty:
        return []
    dates = [cast(pd.Timestamp, index).date() for index in drawdown.index]
    values = [float(value) for value in drawdown]

    episodes: list[_EpisodeRecord] = []
    in_episode = False
    start_index = 0
    peak_date = dates[0]
    for idx, dd_value in enumerate(values):
        if not in_episode and dd_value < 0:
            in_episode = True
            start_index = idx
            peak_date = dates[idx - 1] if idx > 0 else dates[idx]
            continue
        if in_episode and dd_value >= 0:
            segment_values = values[start_index : idx + 1]
            trough_offset = int(np.argmin(segment_values))
            trough_index = start_index + trough_offset
            trough_date = dates[trough_index]
            recovery_date = dates[idx]
            depth = float(min(segment_values))
            days_to_trough = _duration_days(peak_date, trough_date, unit=duration_unit)
            days_to_recovery = _duration_days(trough_date, recovery_date, unit=duration_unit)
            total_days = _duration_days(peak_date, recovery_date, unit=duration_unit)
            episodes.append(
                _EpisodeRecord(
                    peak_date=peak_date,
                    trough_date=trough_date,
                    recovery_date=recovery_date,
                    depth=depth,
                    days_to_trough=days_to_trough,
                    days_to_recovery=days_to_recovery,
                    total_days=total_days,
                    is_recovered=True,
                )
            )
            in_episode = False

    if in_episode:
        segment_values = values[start_index:]
        trough_offset = int(np.argmin(segment_values))
        trough_index = start_index + trough_offset
        trough_date = dates[trough_index]
        depth = float(min(segment_values))
        end_date = dates[-1]
        episodes.append(
            _EpisodeRecord(
                peak_date=peak_date,
                trough_date=trough_date,
                recovery_date=None,
                depth=depth,
                days_to_trough=_duration_days(peak_date, trough_date, unit=duration_unit),
                days_to_recovery=None,
                total_days=_duration_days(peak_date, end_date, unit=duration_unit),
                is_recovered=False,
            )
        )
    return episodes


def _drawdown_summary(
    drawdown: pd.Series,
    *,
    alpha: float,
    duration_unit: str,
) -> tuple[DrawdownSummary, list[_EpisodeRecord]]:
    if drawdown.empty:
        return (
            DrawdownSummary(
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
            ),
            [],
        )

    episodes = _build_episodes(drawdown, duration_unit=duration_unit)
    depths = [episode.depth for episode in episodes]
    dar_value: float | None = None
    cdar_value: float | None = None
    if depths:
        dar_value = float(np.quantile(np.array(depths), 1.0 - alpha, method="linear"))
        worst_tail = [depth for depth in depths if depth <= dar_value]
        if worst_tail:
            cdar_value = float(np.mean(worst_tail))

    max_episode = min(episodes, key=lambda episode: episode.depth) if episodes else None
    dd_values = [float(value) for value in drawdown if float(value) < 0]
    average_drawdown = float(np.mean(dd_values)) if dd_values else 0.0
    ulcer_index = float(sqrt(float(np.mean(np.square(np.array([float(v) for v in drawdown]))))))

    summary = DrawdownSummary(
        max_drawdown=max_episode.depth if max_episode else 0.0,
        max_drawdown_peak_date=max_episode.peak_date if max_episode else None,
        max_drawdown_trough_date=max_episode.trough_date if max_episode else None,
        max_drawdown_recovery_date=max_episode.recovery_date if max_episode else None,
        is_recovered=max_episode.is_recovered if max_episode else True,
        days_to_trough=max_episode.days_to_trough if max_episode else 0,
        days_to_recovery=max_episode.days_to_recovery if max_episode else 0,
        time_under_water_days=int(sum(1 for value in drawdown if float(value) < 0)),
        average_drawdown=average_drawdown,
        ulcer_index=ulcer_index,
        drawdown_at_risk_95=dar_value,
        conditional_drawdown_at_risk_95=cdar_value,
    )
    return summary, episodes


def _to_underwater_series(drawdown: pd.Series) -> list[UnderwaterPoint]:
    points: list[UnderwaterPoint] = []
    for index, value in drawdown.items():
        timestamp = cast(pd.Timestamp, index)
        points.append(UnderwaterPoint(date=timestamp.date(), drawdown=float(value)))
    return points


def _period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


def _build_metadata(
    *,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
    missing_benchmark_policy: str | None,
) -> DrawdownMetadata:
    return DrawdownMetadata(
        include_underwater_series=analysis_options.include_underwater_series,
        include_episode_list=analysis_options.include_episode_list,
        top_n_episodes=analysis_options.top_n_episodes,
        cdar_alpha=analysis_options.cdar_alpha,
        minimum_episode_depth_bps=analysis_options.minimum_episode_depth_bps,
        duration_unit=analysis_options.duration_unit,
        include_benchmark=include_benchmark,
        missing_benchmark_policy=missing_benchmark_policy,
    )


def calculate_drawdown(
    request: DrawdownStatelessInput,
    *,
    input_mode: DrawdownInputMode,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None = None,
    missing_benchmark_policy: str | None = None,
) -> DrawdownResponse:
    returns_df = _build_returns_df(request.returns)
    benchmark_df = _build_returns_df(request.benchmark_returns)
    if returns_df.empty:
        return DrawdownResponse(
            input_mode=input_mode,
            scope=request.scope,
            results={},
            metadata=_build_metadata(
                analysis_options=analysis_options,
                include_benchmark=include_benchmark,
                missing_benchmark_policy=missing_benchmark_policy,
            ),
        )

    open_date = cast(pd.Timestamp, returns_df.index.min()).date()
    results: dict[str, DrawdownPeriodResult] = {}
    for period in request.periods:
        start, end = _resolve_period(
            period.type,
            request.scope.as_of_date,
            open_date,
            year=period.year,
            from_date=period.from_date,
            to_date=period.to_date,
        )
        portfolio_series = _filter_period(returns_df, start=start, end=end)
        if len(portfolio_series) < 1:
            results[_period_name(period)] = DrawdownPeriodResult(
                start_date=start,
                end_date=end,
                summary=None,
                episodes=[],
                relative_to_benchmark=None,
                relative_to_benchmark_context=RelativeDrawdownContext(
                    requested=include_benchmark is True,
                    applied=False,
                    reason=(
                        "BENCHMARK_UNAVAILABLE"
                        if include_benchmark is True
                        else "NOT_REQUESTED"
                    ),
                    aligned_observation_count=0,
                ),
                underwater_series=None,
                error="Insufficient data",
            )
            continue

        wealth = (1 + portfolio_series / 100.0).cumprod()
        running_peak = wealth.cummax()
        drawdown = wealth / running_peak - 1.0
        summary, episodes = _drawdown_summary(
            drawdown,
            alpha=float(analysis_options.cdar_alpha),
            duration_unit=analysis_options.duration_unit,
        )

        min_depth = analysis_options.minimum_episode_depth_bps / 10000.0
        filtered_episodes = [episode for episode in episodes if abs(episode.depth) >= min_depth]
        filtered_episodes = sorted(filtered_episodes, key=lambda episode: episode.depth)[
            : analysis_options.top_n_episodes
        ]
        episode_models = (
            [
                DrawdownEpisode(
                    episode_id=f"dd_{index + 1:04d}",
                    peak_date=episode.peak_date,
                    trough_date=episode.trough_date,
                    recovery_date=episode.recovery_date,
                    depth=episode.depth,
                    days_to_trough=episode.days_to_trough,
                    days_to_recovery=episode.days_to_recovery,
                    total_days=episode.total_days,
                    is_recovered=episode.is_recovered,
                )
                for index, episode in enumerate(filtered_episodes)
            ]
            if analysis_options.include_episode_list
            else []
        )

        relative_summary: RelativeDrawdownSummary | None = None
        relative_context = RelativeDrawdownContext(
            requested=include_benchmark is True,
            applied=False,
            reason="NOT_REQUESTED" if include_benchmark is not True else "BENCHMARK_UNAVAILABLE",
            aligned_observation_count=0,
        )
        if not benchmark_df.empty:
            benchmark_series = _filter_period(benchmark_df, start=start, end=end)
            aligned = pd.merge(
                portfolio_series.to_frame("portfolio"),
                benchmark_series.to_frame("benchmark"),
                left_index=True,
                right_index=True,
                how="inner",
            )
            relative_context = RelativeDrawdownContext(
                requested=include_benchmark is True,
                applied=not aligned.empty,
                reason="APPLIED" if not aligned.empty else "NO_ALIGNED_OBSERVATIONS",
                aligned_observation_count=len(aligned),
            )
            if not aligned.empty:
                active_returns = aligned["portfolio"] - aligned["benchmark"]
                active_wealth = (1 + active_returns / 100.0).cumprod()
                active_peak = active_wealth.cummax()
                active_drawdown = active_wealth / active_peak - 1.0
                active_summary, _ = _drawdown_summary(
                    active_drawdown,
                    alpha=float(analysis_options.cdar_alpha),
                    duration_unit=analysis_options.duration_unit,
                )
                relative_summary = RelativeDrawdownSummary(
                    max_drawdown=active_summary.max_drawdown,
                    max_drawdown_peak_date=active_summary.max_drawdown_peak_date,
                    max_drawdown_trough_date=active_summary.max_drawdown_trough_date,
                    max_drawdown_recovery_date=active_summary.max_drawdown_recovery_date,
                    is_recovered=active_summary.is_recovered,
                    days_to_trough=active_summary.days_to_trough,
                    days_to_recovery=active_summary.days_to_recovery,
                    time_under_water_days=active_summary.time_under_water_days or 0,
                )

        results[_period_name(period)] = DrawdownPeriodResult(
            start_date=start,
            end_date=end,
            summary=summary,
            episodes=episode_models,
            relative_to_benchmark=relative_summary,
            relative_to_benchmark_context=relative_context,
            underwater_series=(
                _to_underwater_series(drawdown)
                if analysis_options.include_underwater_series
                else None
            ),
            error=None,
        )

    return DrawdownResponse(
        input_mode=input_mode,
        scope=request.scope,
        results=results,
        metadata=_build_metadata(
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
            missing_benchmark_policy=missing_benchmark_policy,
        ),
    )
