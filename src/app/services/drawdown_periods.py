from __future__ import annotations

from typing import cast

import pandas as pd

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownEpisode,
    DrawdownPeriodResult,
    DrawdownStatelessInput,
    DrawdownSummary,
    RelativeDrawdownContext,
)
from app.services.drawdown_period_series import (
    DrawdownInputFrames,
    DrawdownPeriodSeries,
    build_input_frames,
    period_series,
)
from app.services.drawdown_relative_benchmark import (
    RelativeBenchmarkResult,
    RelativeBenchmarkSeries,
    relative_benchmark_result,
)
from app.services.drawdown_series import (
    EpisodeRecord,
)
from app.services.drawdown_series import (
    drawdown_from_returns as _drawdown_from_returns,
)
from app.services.drawdown_series import (
    drawdown_summary as _drawdown_summary,
)
from app.services.drawdown_series import (
    to_underwater_series as _to_underwater_series,
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
    relative = _period_relative_benchmark_result(
        period_series,
        analysis_options=analysis_options,
        include_benchmark=include_benchmark,
    )
    return _calculated_period_result(
        period_series,
        analysis_options=analysis_options,
        drawdown=drawdown,
        summary=summary,
        episodes=episodes,
        relative=relative,
    )


def _period_relative_benchmark_result(
    period_series: DrawdownPeriodSeries,
    *,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
) -> RelativeBenchmarkResult:
    return relative_benchmark_result(
        RelativeBenchmarkSeries(
            portfolio_returns=period_series.portfolio_returns,
            benchmark_returns=period_series.benchmark_returns,
            benchmark_available=period_series.benchmark_available,
        ),
        include_benchmark=include_benchmark,
        analysis_options=analysis_options,
    )


def _calculated_period_result(
    period_series: DrawdownPeriodSeries,
    *,
    analysis_options: DrawdownAnalysisOptions,
    drawdown: pd.Series,
    summary: DrawdownSummary,
    episodes: list[EpisodeRecord],
    relative: RelativeBenchmarkResult,
) -> DrawdownPeriodResult:
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
        series = period_series(
            frames=frames,
            request=request,
            period=period,
            open_date=open_date,
        )
        results[series.name] = _calculate_period_result(
            series,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
        )
    return results


__all__ = ["DrawdownInputFrames", "build_input_frames", "drawdown_period_results"]
