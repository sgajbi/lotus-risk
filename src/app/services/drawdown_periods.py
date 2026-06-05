from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from collections.abc import Sequence
from typing import cast

import pandas as pd

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownEpisode,
    DrawdownPeriodResult,
    RelativeDrawdownContext,
    DrawdownStatelessInput,
)
from app.contracts.risk import ReturnPoint, RiskRequestPeriod
from app.services.drawdown_relative_benchmark import (
    RelativeBenchmarkSeries,
    relative_benchmark_result,
)
from app.services.drawdown_series import (
    EpisodeRecord,
    drawdown_from_returns as _drawdown_from_returns,
    drawdown_summary as _drawdown_summary,
    to_underwater_series as _to_underwater_series,
)
from app.services.risk.period_resolution import resolve_period


@dataclass(frozen=True)
class DrawdownInputFrames:
    portfolio: pd.DataFrame
    benchmark: pd.DataFrame


@dataclass(frozen=True)
class DrawdownPeriodSeries:
    name: str
    start: date
    end: date
    portfolio_returns: pd.Series
    benchmark_returns: pd.Series
    benchmark_available: bool


def _build_returns_df(returns: Sequence[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in returns])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _filter_period(df: pd.DataFrame, *, start: date, end: date) -> pd.Series:
    filtered = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)), "value"]
    return filtered


def _period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


def build_input_frames(request: DrawdownStatelessInput) -> DrawdownInputFrames:
    return DrawdownInputFrames(
        portfolio=_build_returns_df(request.returns),
        benchmark=_build_returns_df(request.benchmark_returns),
    )


def _period_series(
    *,
    frames: DrawdownInputFrames,
    request: DrawdownStatelessInput,
    period: RiskRequestPeriod,
    open_date: date,
) -> DrawdownPeriodSeries:
    start, end = resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date,
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    benchmark_returns = (
        _filter_period(frames.benchmark, start=start, end=end)
        if not frames.benchmark.empty
        else pd.Series(dtype="float64")
    )
    return DrawdownPeriodSeries(
        name=_period_name(period),
        start=start,
        end=end,
        portfolio_returns=_filter_period(frames.portfolio, start=start, end=end),
        benchmark_returns=benchmark_returns,
        benchmark_available=not frames.benchmark.empty,
    )


def _insufficient_period_result(
    period_series: DrawdownPeriodSeries,
    *,
    include_benchmark: bool | None,
) -> DrawdownPeriodResult:
    return DrawdownPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        portfolio_observation_count=0,
        benchmark_observation_count=0,
        summary=None,
        episodes=[],
        relative_to_benchmark=None,
        relative_to_benchmark_context=RelativeDrawdownContext(
            requested=include_benchmark is True,
            applied=False,
            reason="BENCHMARK_UNAVAILABLE" if include_benchmark is True else "NOT_REQUESTED",
            aligned_observation_count=0,
        ),
        underwater_series=None,
        error="Insufficient data",
    )


def _episode_models(
    episodes: list[EpisodeRecord],
    *,
    analysis_options: DrawdownAnalysisOptions,
) -> list[DrawdownEpisode]:
    min_depth = analysis_options.minimum_episode_depth_bps / 10000.0
    filtered_episodes = [episode for episode in episodes if abs(episode.depth) >= min_depth]
    filtered_episodes = sorted(filtered_episodes, key=lambda episode: episode.depth)[
        : analysis_options.top_n_episodes
    ]
    if not analysis_options.include_episode_list:
        return []
    return [
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


def _calculate_period_result(
    period_series: DrawdownPeriodSeries,
    *,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
) -> DrawdownPeriodResult:
    if len(period_series.portfolio_returns) < 1:
        return _insufficient_period_result(
            period_series,
            include_benchmark=include_benchmark,
        )

    drawdown = _drawdown_from_returns(period_series.portfolio_returns)
    summary, episodes = _drawdown_summary(
        drawdown,
        alpha=float(analysis_options.cdar_alpha),
        duration_unit=analysis_options.duration_unit,
    )
    relative = relative_benchmark_result(
        RelativeBenchmarkSeries(
            portfolio_returns=period_series.portfolio_returns,
            benchmark_returns=period_series.benchmark_returns,
            benchmark_available=period_series.benchmark_available,
        ),
        include_benchmark=include_benchmark,
        analysis_options=analysis_options,
    )
    return DrawdownPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        portfolio_observation_count=len(period_series.portfolio_returns),
        benchmark_observation_count=len(period_series.benchmark_returns),
        summary=summary,
        episodes=_episode_models(episodes, analysis_options=analysis_options),
        relative_to_benchmark=relative.summary,
        relative_to_benchmark_context=relative.context,
        underwater_series=(
            _to_underwater_series(drawdown) if analysis_options.include_underwater_series else None
        ),
        error=None,
    )


def drawdown_period_results(
    *,
    request: DrawdownStatelessInput,
    frames: DrawdownInputFrames,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
) -> dict[str, DrawdownPeriodResult]:
    open_date = cast(pd.Timestamp, frames.portfolio.index.min()).date()
    results: dict[str, DrawdownPeriodResult] = {}
    for period in request.periods:
        period_series = _period_series(
            frames=frames,
            request=request,
            period=period,
            open_date=open_date,
        )
        results[period_series.name] = _calculate_period_result(
            period_series,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
        )
    return results


__all__ = ["DrawdownInputFrames", "build_input_frames", "drawdown_period_results"]
